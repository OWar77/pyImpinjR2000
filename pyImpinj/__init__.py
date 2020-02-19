# !/usr/bin/python
# -*- coding:utf-8 -*-
""" Library for Impinj R2000 module."""
# Python:   3.6.5+
# Platform: Windows/Linux/MacOS
# Author:   Heyn (heyunhuan@gmail.com)
# Program:  Library for Impinj R2000 module.
# Package:  None.
# Drivers:  None.
# History:  2020-02-18 Ver:1.0 [Heyn] Initialization

__author__    = 'Heyn'
__version__   = '1.0'

import os
import queue
import struct
import serial
import libscrc
import logging
import serial.threaded
import serial.tools.list_ports

from .enums    import ImpinjR2KCommands
from .enums    import ImpinjR2KGlobalErrors
from .enums    import ImpinjR2KFastSwitchInventory

from .protocol import ImpinjR2KProtocols
from .constant import FREQUENCY_TABLES, READER_ANTENNA

class ImpinjProtocolFactory( serial.threaded.FramedPacket ):
    START = b'\xA0'
    def __init__( self, package_queue, command_queue ):
        self.packet = bytearray()
        self.in_packet = False
        self.transport = None
        self.package_queue = package_queue
        self.command_queue = command_queue
        super( ImpinjProtocolFactory, self ).__init__( )

    def __call__( self ):
        return self

    def connection_made( self, transport ):
        self.transport = transport

    def data_received( self, data ):
        # logging.debug( data )
        for byte in serial.iterbytes( data ):
            if ( byte == self.START ) and ( self.in_packet is False ):
                self.in_packet = True
                self.packet.extend( byte )
            elif self.in_packet:
                self.packet.extend( byte )

                if ( ( self.packet[1] + 2 ) == len( self.packet ) ):
                    self.in_packet = False
                    if ( libscrc.lrc( bytes(self.packet) ) == 0 ):
                        self.handle_packet( bytes( self.packet ) )
                    del self.packet[:]

    def handle_packet( self, packet ):
        try:
            command, message = packet[3], packet[4:-1]
        except BaseException as err:
            logging.error( err )
            return
        
        ### Tags 
        if command in [ 
                        ImpinjR2KCommands.REAL_TIME_INVENTORY,
                        ImpinjR2KCommands.ISO18000_6B_INVENTORY,
                        ImpinjR2KCommands.FAST_SWITCH_ANT_INVENTORY,
                        ImpinjR2KCommands.CUSTOMIZED_SESSION_TARGET_INVENTORY ]:
            antenna   = ( ( message[0] & 0x03 ) + 1  )
            frequency = FREQUENCY_TABLES[ ( ( ( message[0] & 0xFC ) >> 2 ) & 0x3F ) ]

            try:
                pc = struct.unpack( '>H', message[1:3] )[0]
            except BaseException:
                if message[1] == ImpinjR2KGlobalErrors.ANTENNA_MISSING_ERROR:
                    self.package_queue.put( dict( type='ERROR', logs='Antenna-{} disconnect.'.format( antenna ) ) )
                return

            size = ( ( pc & 0xF800 ) >> 10 ) & 0x003E
            if size == 0:
                return
            rssi = message[-1] - 129
            epc  = ''.join( [ '%02X' % x for x in message[3:-1] ] )
            self.package_queue.put( dict( type='TAG',
                                          antenna=antenna,
                                          frequency=frequency, rssi=rssi, epc=epc ) )
        else:
            self.command_queue.put( dict( command=command, data=message ) )

    def connection_lost( self, exc ):
        self.transport = None
        logging.debug( '[ERROR] Serial port connection lost.' )
        super( ImpinjProtocolFactory, self ).connection_lost( exc )

class ImpinjR2KReader( object ):

    def analyze_data( method='RESULT' ):
        def decorator( func ):
            def wrapper( self, *args, **kwargs ):
                func( self, *args, **kwargs )
                try:
                    data = self.command_queue.get( timeout=3 )
                    if method == 'DATA':
                        return data['data']
                    else:
                        return ( True if data['data'][0] == ImpinjR2KGlobalErrors.SUCCESS else False, ImpinjR2KGlobalErrors.to_string( data['data'][0] ) )
                except BaseException as err:
                    return str( err )
            return wrapper
        return decorator

    def __init__( self, package_queue, address=0xFF ):
        self.package_queue, self.address = package_queue, address
        self.command_queue = queue.Queue( 1024 )
        self.ser, self.serial_worker = None, None
        super( ImpinjR2KReader, self ).__init__( )

    def __del__( self ):
        self.worker_close( )

    def scan_serial_port( self, description='COM' ):
        """
            device[0] : COMxx
            device[1] : Prolific USB-to-Serial Comm Port (COMxx)
            device[2] : USB VID:PID=067B:2303 SER=6 LOCATION=1-1.1
        """
        for device in list( serial.tools.list_ports.comports() ):
            if description in device[1]:
                yield device[0]

    def connect( self, port='COM1', baudrate=115200 ):
        self.ser = serial.serial_for_url( port, do_not_open=True )
        self.ser.baudrate, self.ser.bytesize = baudrate, 8
        self.ser.parity, self.ser.stopbits = serial.PARITY_NONE, serial.STOPBITS_ONE

        try:
            self.ser.open( )
            if os.name == 'nt':  # sys.platform == 'win32':
                self.ser.set_buffer_size( 1024*10 )
        except BaseException as err:
            raise FileNotFoundError('Could not open serial port {}: {}'.format(self.ser.name, err))

        self.protocol = ImpinjR2KProtocols( address=self.address, serial=self.ser )

        return True

    def worker_start( self ):
        self.protocol_factory = ImpinjProtocolFactory( self.package_queue, self.command_queue )
        self.serial_worker = serial.threaded.ReaderThread( self.ser, self.protocol_factory )
        self.serial_worker.start( )

    def worker_close( self ):
        if self.serial_worker:
            self.serial_worker.close()
        self.serial_worker = None
    
    #-------------------------------------------------

    @analyze_data( 'DATA' )
    def identifier( self ):
        self.protocol.get_reader_identifier( )

    @analyze_data( )
    def set_rf_power( self, antenna1=20, antenna2=20, antenna3=20, antenna4=20 ):
        logging.info( '[SET RF POWER] Antenna1 = {}dBm'.format( antenna1 ) )
        logging.info( '[SET RF POWER] Antenna2 = {}dBm'.format( antenna2 ) )
        logging.info( '[SET RF POWER] Antenna3 = {}dBm'.format( antenna3 ) )
        logging.info( '[SET RF POWER] Antenna4 = {}dBm'.format( antenna4 ) )
        self.protocol.set_rf_power( ant1=antenna1, ant2=antenna2, ant3=antenna3, ant4=antenna4 )

    @analyze_data( 'DATA' )
    def get_rf_power( self ):
        self.protocol.get_rf_power( )

    @analyze_data( )
    def fast_power( self, value=22 ):
        logging.info( '[FAST SET RF POWER] {}dBm'.format( value ) )
        self.protocol.fast_power( value=value )

    @analyze_data( )
    def set_work_antenna( self, antenna=READER_ANTENNA['ANTENNA1'] ):
        self.protocol.set_work_antenna( antenna=antenna )

    @analyze_data( 'DATA' )
    def get_work_antenna( self ):
        self.protocol.get_work_antenna( )

    def rt_inventory( self, repeat=1 ):
        self.protocol.rt_inventory( repeat=repeat )

    def session_inventory( self, session='S1', target='A', repeat=1 ):
        self.protocol.session_inventory( session='S1', target='A', repeat=1 )

    def fast_switch_ant_inventory( self, param = dict( A=ImpinjR2KFastSwitchInventory.ANTENNA1, Aloop=1,
                                                       B=ImpinjR2KFastSwitchInventory.DISABLED, Bloop=1,
                                                       C=ImpinjR2KFastSwitchInventory.DISABLED, Cloop=1,
                                                       D=ImpinjR2KFastSwitchInventory.DISABLED, Dloop=1,
                                                       Interval = 0,
                                                       Repeat   = 1 ) ):
        self.protocol.fast_switch_ant_inventory( param=param )

    @analyze_data( )
    def beeper( self, mode=0 ):
        logging.info( 'BEEPER MODE : {}'.format( mode ) )
        logging.info( """ MODE: \n 0 : Be quiet \n 1 : Sounds after each inventory \n 2 : Every time a tag is read """ )
        self.protocol.beeper( mode=mode )

    def temperature( self ):
        self.protocol.temperature( )
        value  = ImpinjR2KReader.analyze_data( 'DATA' )( lambda x, y : y )( self, None )
        logging.info( 'Reader temperature is {}C'.format( value[1]*( -1 if value[0] == 0 else 1 ) ) )
        return value[1]*( -1 if value[0] == 0 else 1 )

    def di( self, port ):
        """ Read GPIO
            @param -> port = 1 or 2
        """
        assert( port in ( 1, 2 ) )
        self.protocol.gpio( port=port )
        value  = ImpinjR2KReader.analyze_data( 'DATA' )( lambda x, y : y )( self, None )
        return value[0] if port == 1 else value[1]

    @analyze_data( )
    def do( self, port, level=False ):
        """ Write GPIO
            @param -> port = 3 or 4
        """
        assert( port in ( 3, 4 ) )
        logging.info( 'SET GPIO-{} to {}'.format( port, 1 if level else 0 ) )
        self.protocol.gpio( port=port, level=level )

    #-------------------------------------------------
    def inventory( self, repeat=0xFF ):
        self.protocol.inventory( repeat=repeat )
        value  = ImpinjR2KReader.analyze_data( 'DATA' )( lambda x, y : y )( self, None )
        try:
            antenna, tagcount, read_rate, read_total = struct.unpack( '>BHHI', value )
        except BaseException:
            return 0
        logging.info( 'Antenna ID : {}'.format( antenna + 1 ) )
        logging.info( 'Tag count  : {}'.format( tagcount    ) )
        logging.info( 'Read rate  : {}/s'.format( read_rate   ) )
        logging.info( 'Read total : {}'.format( read_total  ) )
        return tagcount

    def get_inventory_buffer_tag_count( self ):
        self.protocol.get_inventory_buffer_tag_count( )
        value = ImpinjR2KReader.analyze_data( 'DATA' )( lambda x, y : y )( self, None )
        count = struct.unpack( '>H', value )[0]
        logging.info( 'Inventory buffer tag count {}'.format( count ) )
        return count

    def __unpack_inventory_buffer( self, data ):
        count, length = struct.unpack( '>HB', data[0:3] )
        if (length + 6) != len( data ):
            return ''

        pc   = struct.unpack( '>H', data[3:5] )[0]
        size = ( ( pc & 0xF800 ) >> 10 ) & 0x003E
        epc  = ''.join( [ '%02X' % x for x in data[5:size+5] ] )

        crc  = struct.unpack( '>H', data[size+5:size+5+2] )[0]
        if crc != ( libscrc.xmodem( data[3:size+5], 0xFFFF ) ^ 0xFFFF ):
            logging.error( 'TAGS CRC16 is ERROR.')
            return ''

        rssi = data[-3]
        ant  = ( data[-2] & 0x03 + 1 )
        invcount = data[-1]

        logging.info( '*'*50 )
        logging.info( 'COUNT    : {}'.format( count ) )
        logging.info( 'EPC      : {}'.format( epc   ) )
        logging.info( 'CRC      : {:X}'.format( crc   ) )
        logging.info( 'RSSI     : {}'.format( rssi  ) )
        logging.info( 'ANT      : {}'.format( ant   ) )
        logging.info( 'INVCOUNT : {}'.format( invcount   ) )

        return epc

    def get_inventory_buffer( self, loop=1 ):
        epc = []
        self.protocol.get_inventory_buffer( )
        for _ in range( loop ):
            value = ImpinjR2KReader.analyze_data( 'DATA' )( lambda x, y : y )( self, None )
            epc.append( self.__unpack_inventory_buffer( value ) )
        return epc

    def get_and_reset_inventory_buffer( self, loop=1 ):
        epc = []
        self.protocol.get_and_reset_inventory_buffer( )
        for _ in range( loop ):
            value = ImpinjR2KReader.analyze_data( 'DATA' )( lambda x, y : y )( self, None )
            epc.append( self.__unpack_inventory_buffer( value ) )
        return epc
    
    @analyze_data( )
    def reset_inventory_buffer( self ):
        self.protocol.reset_inventory_buffer()

    #-------------------------------------------------
