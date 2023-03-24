#!/usr/bin/env python
#
# A Novation Launchpad control suite for Python.
#
# https://github.com/FMMT666/launchpad.py
# 
# FMMT666(ASkr) 01/2013..09/2019..08/2020..01/2021
# www.askrprojects.net
#
#
#
#  >>>
#  >>> NOTICE FOR SPACE USERS:
#  >>>
#  >>>  Yep, this one uses tabs. Tabs everywhere.
#  >>>  Deal with it :-)
#  >>>
#

import string
import random
import sys
import array

from pygame import midi
from pygame import time


try:
	from launchpad_py.charset import *
except ImportError:
	try:
		from charset import *
	except ImportError:
		sys.exit("error loading Launchpad charset")



##########################################################################################
### CLASS Midi
### Midi singleton wrapper
##########################################################################################
class Midi:

	# instance created 
	instanceMidi = None

	#---------------------------------------------------------------------------------------
	#-- init
	#-- Allow only one instance to be created
	#---------------------------------------------------------------------------------------
	def __init__( self ):
		if Midi.instanceMidi is None:
			try:
				Midi.instanceMidi = Midi.__Midi()
			except:
				# TODO: maybe sth like sys.exit()?
				print("unable to initialize MIDI")
				Midi.instanceMidi = None

		self.devIn  = None
		self.devOut = None


	#---------------------------------------------------------------------------------------
	#-- getattr
	#-- Pass all unknown method calls to the inner Midi class __Midi()
	#---------------------------------------------------------------------------------------
	def __getattr__( self, name ):
		return getattr( self.instanceMidi, name )
	

	#-------------------------------------------------------------------------------------
	#--
	#-------------------------------------------------------------------------------------
	def OpenOutput( self, midi_id ):
		if self.devOut is None:
			try:
				# PyGame's default size of the buffer is 4096.
				# Removed code to tune that...
				self.devOut = midi.Output( midi_id, 0 )
			except:
				self.devOut = None
				return False
		return True


	#-------------------------------------------------------------------------------------
	#--
	#-------------------------------------------------------------------------------------
	def CloseOutput( self ):
		if self.devOut is not None:
			#self.devOut.close()
			del self.devOut
			self.devOut = None


	#-------------------------------------------------------------------------------------
	#--
	#-------------------------------------------------------------------------------------
	def OpenInput( self, midi_id, bufferSize = None ):
		if self.devIn is None:
			try:
				# PyGame's default size of the buffer is 4096.
				if bufferSize is None:
					self.devIn = midi.Input( midi_id )
				else:
					# for experiments...
					self.devIn = midi.Input( midi_id, bufferSize )
			except:
				self.devIn = None
				return False
		return True


	#-------------------------------------------------------------------------------------
	#--
	#-------------------------------------------------------------------------------------
	def CloseInput( self ):
		if self.devIn is not None:
			#self.devIn.close()
			del self.devIn
			self.devIn = None


	#-------------------------------------------------------------------------------------
	#--
	#-------------------------------------------------------------------------------------
	def ReadCheck( self ):
		return self.devIn.poll()

		
	#-------------------------------------------------------------------------------------
	#--
	#-------------------------------------------------------------------------------------
	def ReadRaw( self ):
		return self.devIn.read( 1 )


	#-------------------------------------------------------------------------------------
	#-- sends a single, short message
	#-------------------------------------------------------------------------------------
	def RawWrite( self, stat, dat1, dat2 ):
		self.devOut.write_short( stat, dat1, dat2 )

		
	#-------------------------------------------------------------------------------------
	#-- Sends a list of messages. If timestamp is 0, it is ignored.
	#-- Amount of <dat> bytes is arbitrary.
	#-- [ [ [stat, <dat1>, <dat2>, <dat3>], timestamp ],  [...], ... ]
	#-- <datN> fields are optional
	#-------------------------------------------------------------------------------------
	def RawWriteMulti( self, lstMessages ):
		self.devOut.write( lstMessages )

	
	#-------------------------------------------------------------------------------------
	#-- Sends a single system-exclusive message, given by list <lstMessage>
	#-- The start (0xF0) and end bytes (0xF7) are added automatically.
	#-- [ <dat1>, <dat2>, ..., <datN> ]
	#-- Timestamp is not supported and will be sent as '0' (for now)
	#-------------------------------------------------------------------------------------
	def RawWriteSysEx( self, lstMessage, timeStamp = 0 ):
		# There's a bug in PyGame's (Python 3) list-type message handling, so as a workaround,
		# we'll use the string-type message instead...
		#self.devOut.write_sys_ex( timeStamp, [0xf0] + lstMessage + [0xf7] ) # old Python 2

		# array.tostring() deprecated in 3.9; quickfix ahead
		try:
			self.devOut.write_sys_ex( timeStamp, array.array('B', [0xf0] + lstMessage + [0xf7] ).tostring() )
		except:
			self.devOut.write_sys_ex( timeStamp, array.array('B', [0xf0] + lstMessage + [0xf7] ).tobytes() )



	########################################################################################
	### CLASS __Midi
	### The rest of the Midi class, non Midi-device specific.
	########################################################################################
	class __Midi:

		#-------------------------------------------------------------------------------------
		#-- init
		#-------------------------------------------------------------------------------------
		def __init__( self ):
			# exception handling moved up to Midi()
			midi.init()
			# but I can't remember why I put this one in here...
			midi.get_count()

				
		#-------------------------------------------------------------------------------------
		#-- del
		#-- This will never be executed, because no one knows, how many Launchpad instances
		#-- exist(ed) until we start to count them...
		#-------------------------------------------------------------------------------------
		def __del__( self ):
			#midi.quit()
			pass


		#-------------------------------------------------------------------------------------
		#-- Returns a list of devices that matches the string 'name' and has in- or outputs.
		#-------------------------------------------------------------------------------------
		def SearchDevices( self, name, output = True, input = True, quiet = True ):
			ret = []
			i = 0
			
			for n in range( midi.get_count() ):
				md = midi.get_device_info( n )
				if str( md[1].lower() ).find( name.lower() ) >= 0:
					if quiet == False:
						print('%2d' % ( i ), md)
						sys.stdout.flush()
					if output == True and md[3] > 0:
						ret.append( i )
					if input == True and md[2] > 0:
						ret.append( i )
				i += 1

			return ret

			
		#-------------------------------------------------------------------------------------
		#-- Returns the first device that matches the string 'name'.
		#-- NEW2015/02: added number argument to pick from several devices (if available)
		#-------------------------------------------------------------------------------------
		def SearchDevice( self, name, output = True, input = True, number = 0 ):
			ret = self.SearchDevices( name, output, input )
			
			if number < 0 or number >= len( ret ):
				return None

			return ret[number]


		#-------------------------------------------------------------------------------------
		#-- Return MIDI time
		#-------------------------------------------------------------------------------------
		def GetTime( self ):
			return midi.time()
		
	


########################################################################################
### CLASS LaunchpadBase
###
########################################################################################
class LaunchpadBase( object ):

	def __init__( self ):
		self.midi   = Midi() # midi interface instance (singleton)
		self.idOut  = None   # midi id for output
		self.idIn   = None   # midi id for input

		# scroll directions
		self.SCROLL_NONE  =  0
		self.SCROLL_LEFT  = -1
		self.SCROLL_RIGHT =  1

	# LOL; That fixes a years old bug. Officially an idiot now :)
#	def __delete__( self ):
	def __del__( self ):
		self.Close()
		

	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-------------------------------------------------------------------------------------
	def Open( self, number = 0, name = "Launchpad" ):
		self.idOut = self.midi.SearchDevice( name, True, False, number = number )
		self.idIn  = self.midi.SearchDevice( name, False, True, number = number )
		
		if self.idOut is None or self.idIn is None:
			return False

		if self.midi.OpenOutput( self.idOut ) == False:
			return False
		
		return self.midi.OpenInput( self.idIn )


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-------------------------------------------------------------------------------------
	def Check( self, number = 0, name = "Launchpad" ):
		self.idOut = self.midi.SearchDevice( name, True, False, number = number )
		self.idIn  = self.midi.SearchDevice( name, False, True, number = number )
		
		if self.idOut is None or self.idIn is None:
			return False
		
		return True


	#-------------------------------------------------------------------------------------
	#-- Closes this device
	#-------------------------------------------------------------------------------------
	def Close( self ):
		self.midi.CloseInput()
		self.midi.CloseOutput()
	

	#-------------------------------------------------------------------------------------
	#-- prints a list of all devices to the console (for debug)
	#-------------------------------------------------------------------------------------
	def ListAll( self, searchString = '' ):
		self.midi.SearchDevices( searchString, True, True, False )


	#-------------------------------------------------------------------------------------
	#-- Clears the button buffer (The Launchpads remember everything...)
	#-- Because of empty reads (timeouts), there's nothing more we can do here, but
	#-- repeat the polls and wait a little...
	#-------------------------------------------------------------------------------------
	def ButtonFlush( self ):
		doReads = 0
		# wait for that amount of consecutive read fails to exit
		while doReads < 3:
			if self.midi.ReadCheck():
				doReads = 0
				self.midi.ReadRaw()
			else:
				doReads += 1
				time.wait( 5 )


	#-------------------------------------------------------------------------------------
	#-- Returns a list of all MIDI events, empty list if nothing happened.
	#-- Useful for debugging or checking new devices.
	#-------------------------------------------------------------------------------------
	def EventRaw( self ):
		if self.midi.ReadCheck():
			return self.midi.ReadRaw()
		else:
			return []



########################################################################################
### CLASS Launchpad
###
### For 2-color Launchpads with 8x8 matrix and 2x8 top/right rows
########################################################################################
class Launchpad( LaunchpadBase ):

	# LED AND BUTTON NUMBERS IN RAW MODE (DEC):
	#
	# +---+---+---+---+---+---+---+---+ 
	# |200|201|202|203|204|205|206|207| < AUTOMAP BUTTON CODES;
	# +---+---+---+---+---+---+---+---+   Or use LedCtrlAutomap() for LEDs (alt. args)
	# 
	# +---+---+---+---+---+---+---+---+  +---+
	# |  0|...|   |   |   |   |   |  7|  |  8|
	# +---+---+---+---+---+---+---+---+  +---+
	# | 16|...|   |   |   |   |   | 23|  | 24|
	# +---+---+---+---+---+---+---+---+  +---+
	# | 32|...|   |   |   |   |   | 39|  | 40|
	# +---+---+---+---+---+---+---+---+  +---+
	# | 48|...|   |   |   |   |   | 55|  | 56|
	# +---+---+---+---+---+---+---+---+  +---+
	# | 64|...|   |   |   |   |   | 71|  | 72|
	# +---+---+---+---+---+---+---+---+  +---+
	# | 80|...|   |   |   |   |   | 87|  | 88|
	# +---+---+---+---+---+---+---+---+  +---+
	# | 96|...|   |   |   |   |   |103|  |104| 
	# +---+---+---+---+---+---+---+---+  +---+
	# |112|...|   |   |   |   |   |119|  |120|
	# +---+---+---+---+---+---+---+---+  +---+
	# 
	#
	# LED AND BUTTON NUMBERS IN XY MODE (X/Y)
	#
	#   0   1   2   3   4   5   6   7      8   
	# +---+---+---+---+---+---+---+---+ 
	# |   |1/0|   |   |   |   |   |   |         0
	# +---+---+---+---+---+---+---+---+ 
	# 
	# +---+---+---+---+---+---+---+---+  +---+
	# |0/1|   |   |   |   |   |   |   |  |   |  1
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |   |   |   |   |  |   |  2
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |   |5/3|   |   |  |   |  3
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |   |   |   |   |  |   |  4
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |   |   |   |   |  |   |  5
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |4/6|   |   |   |  |   |  6
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |   |   |   |   |  |   |  7
	# +---+---+---+---+---+---+---+---+  +---+
	# |   |   |   |   |   |   |   |   |  |8/8|  8
	# +---+---+---+---+---+---+---+---+  +---+
	#


	#-------------------------------------------------------------------------------------
	#-- reset the Launchpad
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.midi.RawWrite( 176, 0, 0 )


	#-------------------------------------------------------------------------------------
	#-- Returns a Launchpad compatible "color code byte"
	#-- NOTE: In here, number is 0..7 (left..right)
	#-------------------------------------------------------------------------------------
	def LedGetColor( self, red, green ):
		led = 0
		
		red = min( int(red), 3 ) # make int and limit to <=3
		red = max( red, 0 )      # no negative numbers

		green = min( int(green), 3 ) # make int and limit to <=3
		green = max( green, 0 )      # no negative numbers

		led |= red
		led |= green << 4 
		
		return led

		
	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its raw <number>; with <green/red> brightness: 0..3
	#-- For LED numbers, see grid description on top of class.
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, red, green ):

		if number > 199:
			if number < 208:
				# 200-207
				self.LedCtrlAutomap( number - 200, red, green )
		else:
			if number < 0 or number > 120:
				return
			# 0-120
			led = self.LedGetColor( red, green )
			self.midi.RawWrite( 144, number, led )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x> and <y>  with <green/red> brightness 0..3
	#-------------------------------------------------------------------------------------
	def LedCtrlXY( self, x, y, red, green ):

		if x < 0 or x > 8 or y < 0 or y > 8:
			return

		if y == 0:
			self.LedCtrlAutomap( x, red, green )
		
		else:
			self.LedCtrlRaw( ( (y-1) << 4) | x, red, green )


	#-------------------------------------------------------------------------------------
	#-- Sends a list of consecutive, special color values to the Launchpad.
	#-- Only requires (less than) half of the commands to update all buttons.
	#-- [ LED1, LED2, LED3, ... LED80 ]
	#-- First, the 8x8 matrix is updated, left to right, top to bottom.
	#-- Afterwards, the algorithm continues with the rightmost buttons and the
	#-- top "automap" buttons.
	#-- LEDn color format: 00gg00rr <- 2 bits green, 2 bits red (0..3)
	#-- Function LedGetColor() will do the coding for you...
	#-- Notice that the amount of LEDs needs to be even.
	#-- If an odd number of values is sent, the next, following LED is turned off!
	#-- REFAC2015: Device specific.
	#-------------------------------------------------------------------------------------
	def LedCtrlRawRapid( self, allLeds ):
		le = len( allLeds )

		for i in range( 0, le, 2 ):
			self.midi.RawWrite( 146, allLeds[i], allLeds[i+1] if i+1 < le else 0 )

#   This fast version does not work, because the Launchpad gets confused
#   by the timestamps...
#
#		tmsg= []
#		for i in range( 0, le, 2 ):
#			# create a message
#			msg = [ 146 ]
#			msg.append( allLeds[i] )
#			if i+1 < le:
#				msg.append( allLeds[i+1] )
#			# add it to the list
#			tmsg.append( msg )
#			# add a timestanp
#			tmsg.append( self.midi.GetTime() + i*10 )
#
#		self.midi.RawWriteMulti( [ tmsg ] )


	#-------------------------------------------------------------------------------------
	#-- "Homes" the next LedCtrlRawRapid() call, so it will start with the first LED again.
	#-------------------------------------------------------------------------------------
	def LedCtrlRawRapidHome( self ):
		self.midi.RawWrite( 176, 1, 0 )


	#-------------------------------------------------------------------------------------
	#-- Controls an automap LED <number>; with <green/red> brightness: 0..3
	#-- NOTE: In here, number is 0..7 (left..right)
	#-------------------------------------------------------------------------------------
	def LedCtrlAutomap( self, number, red, green ):

		if number < 0 or number > 7:
			return

		red   = min( 0, red )
		red   = max( 7, red )
		green = min( 0, green )
		green = max( 7, green )
		led = self.LedGetColor( red, green )
		
		self.midi.RawWrite( 176, 104 + number, led )


	#-------------------------------------------------------------------------------------
	#-- all LEDs on
	#-- <colorcode> is here for backwards compatibility with the newer "Mk2" and "Pro"
	#-- classes. If it's "0", all LEDs are turned off. In all other cases turned on,
	#-- like the function name implies :-/
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode == 0:
			self.Reset()
		else:
			self.midi.RawWrite( 176, 0, 127 )

		
	#-------------------------------------------------------------------------------------
	#-- Sends character <char> in colors <red/green> and lateral offset <offsx> (-8..8)
	#-- to the Launchpad. <offsy> does not have yet any function
	#-------------------------------------------------------------------------------------
	def LedCtrlChar( self, char, red, green, offsx = 0, offsy = 0 ):
		char = ord( char )
		
		if char < 0 or char > 255:
			return
		char *= 8

		for i in range(0, 8*16, 16):
			for j in range(8):
				lednum = i + j + offsx
				if lednum >= i and lednum < i + 8:
					if CHARTAB[char]  &  0x80 >> j:
						self.LedCtrlRaw( lednum, red, green )
					else:
						self.LedCtrlRaw( lednum, 0, 0 )
			char += 1
					

	#-------------------------------------------------------------------------------------
	#-- Scroll <text>, in colors specified by <red/green>, as fast as we can.
	#-- <direction> specifies: -1 to left, 0 no scroll, 1 to right
	#-- The delays were a dirty hack, but there's little to nothing one can do here.
	#-- So that's how the <waitms> parameter came into play...
	#-- NEW   12/2016: More than one char on display \o/
	#-- IDEA: variable spacing for seamless scrolling, e.g.: "__/\_"
	#-------------------------------------------------------------------------------------
	def LedCtrlString( self, text, red, green, direction = None, waitms = 150 ):

		limit = lambda n, mini, maxi: max(min(maxi, n), mini)

		if direction == self.SCROLL_LEFT:
			text += " "
			for n in range( (len(text) + 1) * 8 ):
				if n <= len(text)*8:
					self.LedCtrlChar( text[ limit( (  n   //16)*2     , 0, len(text)-1 ) ], red, green, 8- n   %16 )
				if n > 7:
					self.LedCtrlChar( text[ limit( (((n-8)//16)*2) + 1, 0, len(text)-1 ) ], red, green, 8-(n-8)%16 )
				time.wait(waitms)
		elif direction == self.SCROLL_RIGHT:
			# TODO: Just a quick hack (screen is erased before scrolling begins).
			#       Characters at odd positions from the right (1, 3, 5), with pixels at the left,
			#       e.g. 'C' will have artifacts at the left (pixel repeated).
			text = " " + text + " " # just to avoid artifacts on full width characters
#			for n in range( (len(text) + 1) * 8 - 1, 0, -1 ):
			for n in range( (len(text) + 1) * 8 - 7, 0, -1 ):
				if n <= len(text)*8:
					self.LedCtrlChar( text[ limit( (  n   //16)*2     , 0, len(text)-1 ) ], red, green, 8- n   %16 )
				if n > 7:
					self.LedCtrlChar( text[ limit( (((n-8)//16)*2) + 1, 0, len(text)-1 ) ], red, green, 8-(n-8)%16 )
				time.wait(waitms)
		else:
			for i in text:
				for n in range(4):  # pseudo repetitions to compensate the timing a bit
					self.LedCtrlChar(i, red, green)
					time.wait(waitms)

					
	#-------------------------------------------------------------------------------------
	#-- Returns True if a button event was received.
	#-------------------------------------------------------------------------------------
	def ButtonChanged( self ):
		return self.midi.ReadCheck()

		
	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change as a list:
	#-- [ <button>, <True/False> ]
	#-------------------------------------------------------------------------------------
	def ButtonStateRaw( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()
			return [ a[0][0][1] if a[0][0][0] == 144 else a[0][0][1] + 96, True if a[0][0][2] > 0 else False ]
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Returns an x/y value of the last button change as a list:
	#-- [ <x>, <y>, <True/False> ]
	#-------------------------------------------------------------------------------------
	def ButtonStateXY( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			if a[0][0][0] == 144:
				x = a[0][0][1] & 0x0f
				y = ( a[0][0][1] & 0xf0 ) >> 4
				
				return [ x, y+1, True if a[0][0][2] > 0 else False ]
				
			elif a[0][0][0] == 176:
				return [ a[0][0][1] - 104, 0, True if a[0][0][2] > 0 else False ]
				
		return []


########################################################################################
### CLASS LaunchpadPro
###
### For 3-color "Pro" Launchpads with 8x8 matrix and 4x8 left/right/top/bottom rows
########################################################################################
class LaunchpadPro( LaunchpadBase ):

	# LED AND BUTTON NUMBERS IN RAW MODE (DEC)
	# WITH LAUNCHPAD IN "LIVE MODE" (PRESS SETUP, top-left GREEN).
	#
	# Notice that the fine manual doesn't know that mode.
	# According to what's written there, the numbering used
	# refers to the "PROGRAMMING MODE", which actually does
	# not react to any of those notes (or numbers).
	#
	#        +---+---+---+---+---+---+---+---+ 
	#        | 91|   |   |   |   |   |   | 98|
	#        +---+---+---+---+---+---+---+---+ 
	#         
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 80|  | 81|   |   |   |   |   |   |   |  | 89|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 70|  |   |   |   |   |   |   |   |   |  | 79|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 60|  |   |   |   |   |   |   | 67|   |  | 69|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 50|  |   |   |   |   |   |   |   |   |  | 59|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 40|  |   |   |   |   |   |   |   |   |  | 49|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 30|  |   |   |   |   |   |   |   |   |  | 39|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 20|  |   |   | 23|   |   |   |   |   |  | 29|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 10|  |   |   |   |   |   |   |   |   |  | 19|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#       
	#        +---+---+---+---+---+---+---+---+ 
	#        |  1|  2|   |   |   |   |   |  8|
	#        +---+---+---+---+---+---+---+---+ 
	#
	#
	# LED AND BUTTON NUMBERS IN XY CLASSIC MODE (X/Y)
	#
	#   9      0   1   2   3   4   5   6   7      8   
	#        +---+---+---+---+---+---+---+---+ 
	#        |0/0|   |2/0|   |   |   |   |   |         0
	#        +---+---+---+---+---+---+---+---+ 
	#         
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |0/1|   |   |   |   |   |   |   |  |   |  1
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |9/2|  |   |   |   |   |   |   |   |   |  |   |  2
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |5/3|   |   |  |   |  3
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  4
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  5
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |4/6|   |   |   |  |   |  6
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  7
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |9/8|  |   |   |   |   |   |   |   |   |  |8/8|  8
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#       
	#        +---+---+---+---+---+---+---+---+ 
	#        |   |1/9|   |   |   |   |   |   |         9
	#        +---+---+---+---+---+---+---+---+ 
	#
	#
	# LED AND BUTTON NUMBERS IN XY PRO MODE (X/Y)
	#
	#   0      1   2   3   4   5   6   7   8      9
	#        +---+---+---+---+---+---+---+---+ 
	#        |1/0|   |3/0|   |   |   |   |   |         0
	#        +---+---+---+---+---+---+---+---+ 
	#         
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |1/1|   |   |   |   |   |   |   |  |   |  1
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |0/2|  |   |   |   |   |   |   |   |   |  |   |  2
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |6/3|   |   |  |   |  3
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  4
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  5
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |5/6|   |   |   |  |   |  6
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  7
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |0/8|  |   |   |   |   |   |   |   |   |  |9/8|  8
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#       
	#        +---+---+---+---+---+---+---+---+ 
	#        |   |2/9|   |   |   |   |   |   |         9
	#        +---+---+---+---+---+---+---+---+ 
	#
	
	COLORS = {'black':0, 'off':0, 'white':3, 'red':5, 'green':17 }

	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-- Uses search string "Pro", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Open( self, number = 0, name = "Pro" ):
		retval = super( LaunchpadPro, self ).Open( number = number, name = name )
		if retval == True:
			# avoid sending this to an Mk2
			if name.lower() == "pro":
				self.LedSetMode( 0 )

		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "Launchpad Pro", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "Launchpad Pro" ):
		return super( LaunchpadPro, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Sets the button layout (and codes) to the set, specified by <mode>.
	#-- Valid options:
	#--  00 - Session, 01 - Drum Rack, 02 - Chromatic Note, 03 - User (Drum)
	#--  04 - Audio, 05 -Fader, 06 - Record Arm, 07 - Track Select, 08 - Mute
	#--  09 - Solo, 0A - Volume 
	#-- Until now, we'll need the "Session" (0x00) settings.
	#-------------------------------------------------------------------------------------
	# TODO: ASkr, Undocumented!
	# TODO: return value
	def LedSetLayout( self, mode ):
		if mode < 0 or mode > 0x0d:
			return
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 34, mode ] )
		time.wait(10)


	#-------------------------------------------------------------------------------------
	#-- Selects the Pro's mode.
	#-- <mode> -> 0 -> "Ableton Live mode"  (what we need)
	#--           1 -> "Standalone mode"    (power up default)
	#-------------------------------------------------------------------------------------
	def LedSetMode( self, mode ):
		if mode < 0 or mode > 1:
			return
			
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 33, mode ] )
		time.wait(10)


	#-------------------------------------------------------------------------------------
	#-- Sets BPM for pulsing or flashing LEDs
	#-- EXPERIMENTAL FAKE SHOW
	#-- The Launchpad Pro (and Mk2) derive the LED's pulsing or flashing frequency from
	#-- the repetive occurrence of MIDI beat clock messages (msg 248), 24 per beat.
	#-- No timers/events here yet, so we fake it by sending the minimal amount of
	#-- messages (25 for Pro, 26 for Mk2 (not kidding) => 28, probably safe value) once.
	#-- The Pro and the Mk2 support 40..240 BPM, so the maximum time we block everything
	#-- is, for 40 BPM:
	#--   [ 1 / ( 40 BPM * 24 / 60s ) ] * 28 = 1.75s    ; (acrually one less, 28-1)
	#-- Due to the 1ms restriction, the BPMs get quite coarse towards the faster end:
	#--   250, 227, 208, 192, 178, 166, 156, 147, 138, 131...
	#-------------------------------------------------------------------------------------
	def LedCtrlBpm( self, bpm ):
		bpm = min( int( bpm ), 240 )  # limit to upper 240
		bpm = max( bpm, 40 )          # limit to lower 40

		# basically int( 1000 / ( bpm * 24 / 60.0 ) ):
		td = int( 2500 / bpm )

		for _ in range( 28 ):
			self.midi.RawWrite( 248, 0, 0 )
			time.wait( td )


	#-------------------------------------------------------------------------------------
	#-- Returns an RGB colorcode by trying to find a color of a name given by string <name>.
	#-- If nothing was found, Code 'black' (off) is returned.
	#-------------------------------------------------------------------------------------
	def LedGetColorByName( self, name ):
		# should not be required
		#if type( name ) is not str:
		#	return 0;
		if name in LaunchpadPro.COLORS:
			return LaunchpadPro.COLORS[name]
		else:
			return LaunchpadPro.COLORS['black']


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color, specified by
	#-- <red>, <green> and <blue> intensities, with can each be an integer between 0..63.
	#-- If <blue> is omitted, this methos runs in "Classic" compatibility mode and the
	#-- intensities, which were within 0..3 in that mode, are multiplied by 21 (0..63)
	#-- to emulate the old brightness feeling :)
	#-- Notice that each message requires 10 bytes to be sent. For a faster, but
	#-- unfortunately "not-RGB" method, see "LedCtrlRawByCode()"
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, red, green, blue = None ):

		if number < 0 or number > 99:
			return

		if blue is None:
			blue   = 0
			red   *= 21
			green *= 21

		limit = lambda n, mini, maxi: max(min(maxi, n), mini)
		
		red   = limit( red,   0, 63 )
		green = limit( green, 0, 63 )
		blue  = limit( blue,  0, 63 )
			
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 11, number, red, green, blue ] )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color code <colorcode>
	#-- from the Launchpad's color palette.
	#-- If <colorcode> is omitted, 'white' is used.
	#-- This method should be ~3 times faster that the RGB version "LedCtrlRaw()", which
	#-- uses 10 byte, system-exclusive MIDI messages.
	#-------------------------------------------------------------------------------------
	def LedCtrlRawByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		# TODO: limit/check colorcode
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		self.midi.RawWrite( 144, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlRawByCode, but with a pulsing LED.
	#-- Pulsing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlPulseByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		# TODO: limit/check colorcode
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		# for Mk2: [ 0, 32, 41, 2, *24*, 40, *0*, number, colorcode ] (also an error in the docs)
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 40, number, colorcode ] )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlPulseByCode, but with a dual color flashing LED.
	#-- The first color is the one that is already enabled, the second one is the
	#-- <colorcode> argument in this method.
	#-- Flashing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlFlashByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		# TODO: limit/check colorcode
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		# for Mk2: [ 0, 32, 41, 2, *24*, *35*, *0*, number, colorcode ] (also an error in the docs)
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 35, number, colorcode ] )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x>, <y> and <reg>, <green> and <blue>
	#-- intensity values. By default, the old and compatible "Classic" mode is used
	#-- (8x8 matrix left has x=0). If <mode> is set to "pro", x=0 will light up the round
	#-- buttons on the left of the Launchpad Pro (not available on other models).
	#-- This method internally uses "LedCtrlRaw()". Please also notice the comments
	#-- in that one.
	#-------------------------------------------------------------------------------------
	def LedCtrlXY( self, x, y, red, green, blue = None, mode = "classic" ):

		if x < 0 or x > 9 or y < 0 or y > 9:
			return
		
		# rotate matrix to the right, column 9 overflows from right to left, same row
		if mode != "pro":
			x = ( x + 1 ) % 10
			
		# swap y
		led = 90-(10*y) + x
		
		self.LedCtrlRaw( led, red, green, blue )
	

	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x>, <y> and its <colorcode>.
	#-- By default, the old and compatible "Classic" mode is used (8x8 matrix left has x=0).
	#-- If <mode> is set to "pro", x=0 will light up the round buttons on the left of the
	#-- Launchpad Pro (not available on other models).
	#-- About three times faster than the SysEx RGB method LedCtrlXY().
	#-------------------------------------------------------------------------------------
	def LedCtrlXYByCode( self, x, y, colorcode, mode = "classic" ):

		if x < 0 or x > 9 or y < 0 or y > 9:
			return
		
		# rotate matrix to the right, column 9 overflows from right to left, same row
		if mode != "pro":
			x = ( x + 1 ) % 10
			
		# swap y
		led = 90-(10*y) + x
		
		self.LedCtrlRawByCode( led, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Pulses a grid LED by its coordinates <x>, <y> and its <colorcode>.
	#-- By default, the old and compatible "Classic" mode is used (8x8 matrix left has x=0).
	#-- If <mode> is set to "pro", x=0 will light up the round buttons on the left of the
	#-- Launchpad Pro (not available on other models).
	#-------------------------------------------------------------------------------------
	def LedCtrlPulseXYByCode( self, x, y, colorcode, mode = "classic" ):

		if x < 0 or x > 9 or y < 0 or y > 9:
			return
		
		# rotate matrix to the right, column 9 overflows from right to left, same row
		if mode != "pro":
			x = ( x + 1 ) % 10
			
		# swap y
		led = 90-(10*y) + x
		
		self.LedCtrlPulseByCode( led, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Flashes a grid LED by its coordinates <x>, <y> and its <colorcode>.
	#-- By default, the old and compatible "Classic" mode is used (8x8 matrix left has x=0).
	#-- If <mode> is set to "pro", x=0 will light up the round buttons on the left of the
	#-- Launchpad Pro (not available on other models).
	#-------------------------------------------------------------------------------------
	def LedCtrlFlashXYByCode( self, x, y, colorcode, mode = "classic" ):

		if x < 0 or x > 9 or y < 0 or y > 9:
			return
		
		# rotate matrix to the right, column 9 overflows from right to left, same row
		if mode != "pro":
			x = ( x + 1 ) % 10
			
		# swap y
		led = 90-(10*y) + x
		
		self.LedCtrlFlashByCode( led, colorcode )


	#-------------------------------------------------------------------------------------
	#-- New approach to color arguments.
	#-- Controls a grid LED by its coordinates <x>, <y> and a list of colors <lstColor>.
	#-- <lstColor> is a list of length 3, with RGB color information, [<r>,<g>,<b>]
	#-------------------------------------------------------------------------------------
	def LedCtrlXYByRGB( self, x, y, lstColor, mode = "classic" ):

		if type( lstColor ) is not list or len( lstColor ) < 3:
			return

		if x < 0 or x > 9 or y < 0 or y > 9:
			return

		# rotate matrix to the right, column 9 overflows from right to left, same row
		if mode.lower() != "pro":
			x = ( x + 1 ) % 10
			
		# swap y
		led = 90-(10*y) + x
	
		self.LedCtrlRaw( led, lstColor[0], lstColor[1], lstColor[2] )


	#-------------------------------------------------------------------------------------
	#-- Sends character <char> in colors <red/green/blue> and lateral offset <offsx> (-8..8)
	#-- to the Launchpad. <offsy> does not have yet any function.
	#-- If <blue> is omitted, this method runs in "Classic" compatibility mode and the
	#-- old 0..3 <red/green> values are multiplied with 21, to match the "Pro" 0..63 range.
	#-------------------------------------------------------------------------------------
	def LedCtrlChar( self, char, red, green, blue = None, offsx = 0, offsy = 0 ):
		char = ord( char )
		char = min( char, 255)
		char = max( char, 0) * 8

		# compatibility mode
		if blue is None:
			red   *= 21
			green *= 21
			blue   =  0

		for i in range(81, 1, -10):
			for j in range(8):
				sum = i + j + offsx
				if sum >= i and sum < i + 8:
					if CHARTAB[char]  &  0x80 >> j:
						self.LedCtrlRaw( sum, red, green, blue )
					else:
						self.LedCtrlRaw( sum, 0, 0, 0 )
			char += 1


	#-------------------------------------------------------------------------------------
	#-- Scroll <text>, with color specified by <red/green/blue>, as fast as we can.
	#-- <direction> specifies: -1 to left, 0 no scroll, 1 to right
	#-- If <blue> is omitted, "Classic" compatibility mode is turned on and the old
	#-- 0..3 color intensity range is streched by 21 to 0..63.
	#--
	#-- NEW   12/2016: More than one char on display \o/
	#-- IDEA: variable spacing for seamless scrolling, e.g.: "__/\_"
	#-- TODO: That <blue> compatibility thing sucks... Should be removed.
	#-------------------------------------------------------------------------------------
	def LedCtrlString( self, text, red, green, blue = None, direction = None, waitms = 150 ):

		# compatibility mode
		if blue is None:
			red   *= 21
			green *= 21
			blue   =  0
			
		limit = lambda n, mini, maxi: max(min(maxi, n), mini)

		if direction == self.SCROLL_LEFT:
			text += " " # just to avoid artifacts on full width characters
			for n in range( (len(text) + 1) * 8 ):
				if n <= len(text)*8:
					self.LedCtrlChar( text[ limit( (  n   //16)*2     , 0, len(text)-1 ) ], red, green, blue, 8- n   %16 )
				if n > 7:
					self.LedCtrlChar( text[ limit( (((n-8)//16)*2) + 1, 0, len(text)-1 ) ], red, green, blue, 8-(n-8)%16 )
				time.wait(waitms)
		elif direction == self.SCROLL_RIGHT:
			# TODO: Just a quick hack (screen is erased before scrolling begins).
			#       Characters at odd positions from the right (1, 3, 5), with pixels at the left,
			#       e.g. 'C' will have artifacts at the left (pixel repeated).
			text = " " + text + " " # just to avoid artifacts on full width characters
#			for n in range( (len(text) + 1) * 8 - 1, 0, -1 ):
			for n in range( (len(text) + 1) * 8 - 7, 0, -1 ):
				if n <= len(text)*8:
					self.LedCtrlChar( text[ limit( (  n   //16)*2     , 0, len(text)-1 ) ], red, green, blue, 8- n   %16 )
				if n > 7:
					self.LedCtrlChar( text[ limit( (((n-8)//16)*2) + 1, 0, len(text)-1 ) ], red, green, blue, 8-(n-8)%16 )
				time.wait(waitms)
		else:
			for i in text:
				for n in range(4):  # pseudo repetitions to compensate the timing a bit
					self.LedCtrlChar(i, red, green, blue)
					time.wait(waitms)


	#-------------------------------------------------------------------------------------
	#-- Quickly sets all all LEDs to the same color, given by <colorcode>.
	#-- If <colorcode> is omitted, "white" is used.
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']
		else:
			colorcode = min( colorcode, 127 )
			colorcode = max( colorcode, 0 )
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 14, colorcode ] )


	#-------------------------------------------------------------------------------------
	#-- (fake to) reset the Launchpad
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.LedAllOn( 0 )


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <button>, <value> ], in which <button> is the raw number of the button and
	#-- <value> an intensity value from 0..127.
	#-- >0 = button pressed; 0 = button released
	#-- Notice that this is not (directly) compatible with the original ButtonStateRaw()
	#-- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
	#-- Compatibility would require checking via "== True" and not "is True".
	#-- Pressure events are returned if enabled via "returnPressure".
	#-- To distinguish pressure events from buttons, a fake button code of "255" is used,
	#-- so the list looks like [ 255, <value> ].
	#-------------------------------------------------------------------------------------
	def ButtonStateRaw( self, returnPressure = False ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			# Note:
			#  Beside "144" (Note On, grid buttons), "208" (Pressure Value, grid buttons) and
			#  "176" (Control Change, outer buttons), random (broken) SysEx messages
			#  can appear here:
			#   ('###', [[[240, 0, 32, 41], 4]])
			#   ('-->', [])
			#   ('###', [[[2, 16, 45, 0], 4]])
			#   ('###', [[[247, 0, 0, 0], 4]])
			#  ---
			#   ('###', [[[240, 0, 32, 41], 4]])
			#   ('-->', [])
			#  1st one is a SysEx Message (240, 0, 32, 41, 2, 16 ), with command Mode Status (45)
			#  in "Ableton Mode" (0) [would be 1 for Standalone Mode). "247" is the SysEx termination.
			#  Additionally, it's interrupted by a read failure.
			#  The 2nd one is simply cut. Notice that that these are commands usually send TO the
			#  Launchpad...
			#
			# Reminder for the "pressure event issue":
			# The pressure events do not send any button codes, it's really just the pressure,
			# everytime a value changes:
			#   [[[144, 55, 5, 0], 654185]]    button hit ("NoteOn with vel > 0")
			#   [[[208, 24, 0, 0], 654275]]    button hold
			#   [[[208, 127, 0, 0], 654390]]    ...
			#   [[[208, 122, 0, 0], 654506]     ...
			#   [[[208, 65, 0, 0], 654562]]     ...
			#   [[[208, 40, 0, 0], 654567]]     ...
			#   [[[208, 0, 0, 0], 654573]]      ...
			#   [[[144, 55, 0, 0], 654614]]    button released ("NoteOn with vel == 0")
			# When multiple buttons are pressed (hold), the biggest number will be returned.
			#
			# Copied over from the XY method.
			# Try to avoid getting flooded with pressure events
			if returnPressure == False:
				while a[0][0][0] == 208:
					a = self.midi.ReadRaw()
					if a == []:
						return []

			if a[0][0][0] == 144 or a[0][0][0] == 176:
				return [ a[0][0][1], a[0][0][2] ]
			else:
				if returnPressure:
					if a[0][0][0] == 208:
						return [ 255, a[0][0][1] ]
					else:
						return []
				else:
					return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
	#-- <value> is the intensity from 0..127.
	#-- >0 = button pressed; 0 = button released
	#-- Notice that this is not (directly) compatible with the original ButtonStateRaw()
	#-- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
	#-- Compatibility would require checking via "== True" and not "is True".
	#-------------------------------------------------------------------------------------
	def ButtonStateXY( self, mode = "classic", returnPressure = False ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			if returnPressure == False:
				while a[0][0][0] == 208:
					a = self.midi.ReadRaw()
					if a == []:
						return []

			if a[0][0][0] == 144 or a[0][0][0] == 176:
			
				if mode.lower() != "pro":
					x = (a[0][0][1] - 1) % 10
				else:
					x = a[0][0][1] % 10
				y = ( 99 - a[0][0][1] ) // 10
			
				return [ x, y, a[0][0][2] ]
			else:
				if a[0][0][0] == 208:
					return [ 255, 255, a[0][0][1] ]
				else:
					return []
		else:
			return []



########################################################################################
### CLASS LaunchpadMk2
###
### For 3-color "Mk2" Launchpads with 8x8 matrix and 2x8 right/top rows
########################################################################################
class LaunchpadMk2( LaunchpadPro ):

	# LED AND BUTTON NUMBERS IN RAW MODE (DEC)
	#
	# Notice that the fine manual doesn't know that mode.
	# According to what's written there, the numbering used
	# refers to the "PROGRAMMING MODE", which actually does
	# not react to any of those notes (or numbers).
	#
	#        +---+---+---+---+---+---+---+---+ 
	#        |104|   |106|   |   |   |   |111|
	#        +---+---+---+---+---+---+---+---+ 
	#         
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 81|   |   |   |   |   |   |   |  | 89|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 71|   |   |   |   |   |   |   |  | 79|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 61|   |   |   |   |   | 67|   |  | 69|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 51|   |   |   |   |   |   |   |  | 59|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 41|   |   |   |   |   |   |   |  | 49|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 31|   |   |   |   |   |   |   |  | 39|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 21|   | 23|   |   |   |   |   |  | 29|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 11|   |   |   |   |   |   |   |  | 19|
	#        +---+---+---+---+---+---+---+---+  +---+
	#       
	#
	#
	# LED AND BUTTON NUMBERS IN XY MODE (X/Y)
	#
	#          0   1   2   3   4   5   6   7      8   
	#        +---+---+---+---+---+---+---+---+ 
	#        |0/0|   |2/0|   |   |   |   |   |         0
	#        +---+---+---+---+---+---+---+---+ 
	#         
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |0/1|   |   |   |   |   |   |   |  |   |  1
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  2
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |5/3|   |   |  |   |  3
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  4
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  5
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |4/6|   |   |   |  |   |  6
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  7
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |8/8|  8
	#        +---+---+---+---+---+---+---+---+  +---+
	#       


	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-- Uses search string "Mk2", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def Open( self, number = 0, name = "Mk2" ):
		return super( LaunchpadMk2, self ).Open( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "Mk2", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def Check( self, number = 0, name = "Mk2" ):
		return super( LaunchpadMk2, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Quickly sets all all LEDs to the same color, given by <colorcode>.
	#-- If <colorcode> is omitted, "white" is used.
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']
		else:
			colorcode = min( colorcode, 127 )
			colorcode = max( colorcode, 0 )
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 24, 14, colorcode ] )


	#-------------------------------------------------------------------------------------
	#-- (fake to) reset the Launchpad
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.LedAllOn( 0 )


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
	#-- <svalue> the intensity. Because the Mk2 does not come with full analog capabilities,
	#-- unlike the "Pro", the intensity values for the "Mk2" are either 0 or 127.
	#-- 127 = button pressed; 0 = button released
	#-- Notice that this is not (directly) compatible with the original ButtonStateRaw()
	#-- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
	#-- Compatibility would require checking via "== True" and not "is True".
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def ButtonStateXY( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()
			
			if a[0][0][0] == 144 or a[0][0][0] == 176:

				if a[0][0][1] >= 104:
					x = a[0][0][1] - 104
					y = 0
				else:
					x = ( a[0][0][1] - 1) % 10
					y = ( 99 - a[0][0][1] ) // 10
			
				return [ x, y, a[0][0][2] ]
			else:
				return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color, specified by
	#-- <red>, <green> and <blue> intensities, with can each be an integer between 0..63.
	#-- If <blue> is omitted, this methos runs in "Classic" compatibility mode and the
	#-- intensities, which were within 0..3 in that mode, are multiplied by 21 (0..63)
	#-- to emulate the old brightness feeling :)
	#-- Notice that each message requires 10 bytes to be sent. For a faster, but
	#-- unfortunately "not-RGB" method, see "LedCtrlRawByCode()"
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlRaw( self, number, red, green, blue = None ):

		number = min( number, 111 )
		number = max( number, 0 )

		if number > 89 and number < 104:
			return

		if blue is None:
			blue   = 0
			red   *= 21
			green *= 21

		limit = lambda n, mini, maxi: max(min(maxi, n), mini)

		red   = limit( red,   0, 63 )
		green = limit( green, 0, 63 )
		blue  = limit( blue,  0, 63 )
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 16, 11, number, red, green, blue ] )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color code <colorcode>
	#-- from the Launchpad's color palette.
	#-- If <colorcode> is omitted, 'white' is used.
	#-- This method should be ~3 times faster that the RGB version "LedCtrlRaw()", which
	#-- uses 10 byte, system-exclusive MIDI messages.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlRawByCode( self, number, colorcode = None ):

		number = min( number, 111 )
		number = max( number, 0 )

		if number > 89 and number < 104:
			return

		# TODO: limit/check colorcode
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		if number < 104:
			self.midi.RawWrite( 144, number, colorcode )
		else:
			self.midi.RawWrite( 176, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlRawByCode, but with a pulsing LED.
	#-- Pulsing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlPulseByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		# TODO: limit/check colorcode
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		# for Pro: [ 0, 32, 41, 2, *16*, 40, number, colorcode ]
		# Also notice the error in the Mk2 docs. "number" is actually the 2nd
		# command, following an unused "0" (that's also missing in the Pro's command)
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 24, 40, 0, number, colorcode ] )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlPulseByCode, but with a dual color flashing LED.
	#-- The first color is the one that is already enabled, the second one is the
	#-- <colorcode> argument in this method.
	#-- Flashing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlFlashByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		# TODO: limit/check colorcode
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		# for Pro: [ 0, 32, 41, 2, *16*, *35*, number, colorcode ] (also an error in the docs)
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 24, 35, 0, number, colorcode ] )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x>, <y> and <reg>, <green> and <blue>
	#-- intensity values.
	#-- This method internally uses "LedCtrlRaw()".
	#-- Please also notice the comments in that one.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlXY( self, x, y, red, green, blue = None ):

		if x < 0 or x > 8 or y < 0 or y > 8:
			return

		# top row (round buttons)
		if y == 0:
			led = 104 + x
		else:
			# swap y
			led = 91-(10*y) + x
		
		self.LedCtrlRaw( led, red, green, blue )


	#-------------------------------------------------------------------------------------
	#-- New approach to color arguments.
	#-- Controls a grid LED by its coordinates <x>, <y> and a list of colors <lstColor>.
	#-- <lstColor> is a list of length 3, with RGB color information, [<r>,<g>,<b>]
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlXYByRGB( self, x, y, lstColor ):

		if type( lstColor ) is not list or len( lstColor ) < 3:
			return

		if x < 0 or x > 8 or y < 0 or y > 8:
			return

		# top row (round buttons)
		if y == 0:
			led = 104 + x
		else:
			# swap y
			led = 91-(10*y) + x

		self.LedCtrlRaw( led, lstColor[0], lstColor[1], lstColor[2] )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x>, <y> and its <colorcode>.
	#-- About three times faster than the, indeed much more comfortable RGB version
	#-- "LedCtrlXY()"
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlXYByCode( self, x, y, colorcode ):

		if x < 0 or x > 8 or y < 0 or y > 8:
			return

		# top row (round buttons)
		if y == 0:
			led = 104 + x
		else:
			# swap y
			led = 91-(10*y) + x
		
		self.LedCtrlRawByCode( led, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Pulses a grid LED by its coordinates <x>, <y> and its <colorcode>.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlPulseXYByCode( self, x, y, colorcode ):

		if x < 0 or x > 8 or y < 0 or y > 8:
			return

		# top row (round buttons)
		if y == 0:
			led = 104 + x
		else:
			# swap y
			led = 91-(10*y) + x
		
		self.LedCtrlPulseByCode( led, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Flashes a grid LED by its coordinates <x>, <y> and its <colorcode>.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def LedCtrlFlashXYByCode( self, x, y, colorcode ):

		if x < 0 or x > 8 or y < 0 or y > 8:
			return

		# top row (round buttons)
		if y == 0:
			led = 104 + x
		else:
			# swap y
			led = 91-(10*y) + x
		
		self.LedCtrlFlashByCode( led, colorcode )


########################################################################################
### CLASS LaunchControlXL
###
### For 2-color Launch Control XL 
########################################################################################
class LaunchControlXL( LaunchpadBase ):

	# LED, BUTTON AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
	#         
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     | 13| 29| 45| 61| 77| 93|109|125|  |NOP||NOP| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     | 14| 30| 46| 62| 78| 94|110|126|  |104||105| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     | 15| 31| 47| 63| 79| 95|111|127|  |106||107| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     
	#     +---+---+---+---+---+---+---+---+     +---+
	#     |   |   |   |   |   |   |   |   |     |105| 
	#     |   |   |   |   |   |   |   |   |     +---+
	#     |   |   |   |   |   |   |   |   |     |106| 
	#     | 77| 78| 79| 80| 81| 82| 83| 84|     +---+
	#     |   |   |   |   |   |   |   |   |     |107| 
	#     |   |   |   |   |   |   |   |   |     +---+
	#     |   |   |   |   |   |   |   |   |     |108| 
	#     +---+---+---+---+---+---+---+---+     +---+
	#     
	#     +---+---+---+---+---+---+---+---+  
	#     | 41| 42| 43| 44| 57| 58| 59| 60| 
	#     +---+---+---+---+---+---+---+---+  
	#     | 73| 74| 75| 76| 89| 90| 91| 92| 
	#     +---+---+---+---+---+---+---+---+
	#
	#
	# LED NUMBERS IN X/Y MODE (DEC)
	#
	#       0   1   2   3   4   5   6   7      8    9
	#      
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  0  |0/1|   |   |   |   |   |   |   |  |NOP||NOP|  0
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  1  |   |   |   |   |   |   |   |   |  |   ||   |  1
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  2  |   |   |   |   |   |5/2|   |   |  |   ||   |  2
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#                                            8/9
	#     +---+---+---+---+---+---+---+---+     +---+
	#     |   |   |   |   |   |   |   |   |     |   |    3(!)
	#     |   |   |   |   |   |   |   |   |     +---+
	#     |   |   |   |   |   |   |   |   |     |   |    4(!)
	#  3  |   |   |2/3|   |   |   |   |   |     +---+
	#     |   |   |   |   |   |   |   |   |     |   |    5(!)
	#     |   |   |   |   |   |   |   |   |     +---+
	#     |   |   |   |   |   |   |   |   |     |   |    6
	#     +---+---+---+---+---+---+---+---+     +---+
	#     
	#     +---+---+---+---+---+---+---+---+  
	#  4  |   |   |   |   |   |   |   |   |              4(!)
	#     +---+---+---+---+---+---+---+---+  
	#  5  |   |   |   |3/4|   |   |   |   |              5(!)
	#     +---+---+---+---+---+---+---+---+  
	#
	#



	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Control XL MIDI devices.
	#-- Uses search string "Control XL", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Open( self, number = 0, name = "Control XL", template = 1 ):

		# The user template number adds to the MIDI commands.
		# Make sure that the Control XL is set to the corresponding mode by
		# holding down one of the template buttons and selecting the template
		# with the lowest button row 1..8
		# By default, user template 1 is enabled. Notice that the Launch Control
		# actually uses 0..15, but as the pad buttons are labeled 1..8 it probably
		# make sense to use these human readable ones instead.

		template = min( int(template), 16 ) # make int and limit to <=8
		template = max( template, 1 )       # no negative numbers

		self.UserTemplate = template
		
		retval = super( LaunchControlXL, self ).Open( number = number, name = name )
		if retval == True:
			self.TemplateSet( self.UserTemplate )

		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "Pro", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "Control XL" ):
		return super( LaunchControlXL, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Sets the layout template.
	#-- 1..8 selects the user and 9..16 the factory setups.
	#-------------------------------------------------------------------------------------
	def TemplateSet( self, templateNum ):
		if templateNum < 1 or templateNum > 16:
			return
		else:
			self.UserTemplate = templateNum
			self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 17, 119, templateNum-1 ] )


	#-------------------------------------------------------------------------------------
	#-- reset the Launchpad; only reset the current template
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.midi.RawWrite( 176 + self.UserTemplate-1, 0, 0 )


	#-------------------------------------------------------------------------------------
	#-- all LEDs on
	#-- <colorcode> is here for backwards compatibility with the newer "Mk2" and "Pro"
	#-- classes. If it's "0", all LEDs are turned off. In all other cases turned on,
	#-- like the function name implies :-/
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode is None or colorcode == 0:
			self.Reset()
		else:
			self.midi.RawWrite( 176, 0, 127 )


	#-------------------------------------------------------------------------------------
	#-- Returns a Launchpad compatible "color code byte"
	#-- NOTE: In here, number is 0..7 (left..right)
	#-------------------------------------------------------------------------------------
	def LedGetColor( self, red, green ):
		# TODO: copy and clear bits
		led = 0
		
		red = min( int(red), 3 ) # make int and limit to <=3
		red = max( red, 0 )      # no negative numbers

		green = min( int(green), 3 ) # make int and limit to <=3
		green = max( green, 0 )      # no negative numbers

		led |= red
		led |= green << 4 
		
		return led


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its raw <number>; with <green/red> brightness: 0..3
	#-- For LED numbers, see grid description on top of class.
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, red, green ):
		# the order of the LEDs is really a mess
		led = self.LedGetColor( red, green )
		self.midi.RawWrite( 144, number, led )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x> and <y>  with <green/red> brightness 0..3
	#-------------------------------------------------------------------------------------
	def LedCtrlXY( self, x, y, red, green ):
		# TODO: Note about the y coords
		if x < 0 or x > 9 or y < 0 or y > 6:
			return

		if x < 8:
			color = self.LedGetColor( red, green )
		else:
			# the "special buttons" only have one color
			color = self.LedGetColor( 3, 3 )
			

		# TODO: double code ahead ("37 + y"); query "y>2" first, then x...

		if x < 8:
			if y < 3:
				index = y*8 + x
			elif y > 3 and y < 6:
				# skip row 3 and continue with 4 and 5
				index = ( y-1 )*8 + x
			else:
				return
		#-----
		elif x == 8:
			#----- device, mute, solo, record
			if y > 2:
				index = 37 + y
			#----- up
			elif y == 1:
				index = 44
			#----- left
			elif y == 2:
				index = 46
			else:
				return
		#-----
		elif x == 9:
			#----- device, mute, solo, record
			if y > 2:
				index = 37 + y
			#----- down
			elif y == 1:
				index = 45
			#----- right
			elif y == 2:
				index = 47
			else:
				return

		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 17, 120, 0, index, color ] )


	#-------------------------------------------------------------------------------------
	#-- Clears the input buffer (The Launchpads remember everything...)
	#-------------------------------------------------------------------------------------
	def InputFlush( self ):
		return self.ButtonFlush()


	#-------------------------------------------------------------------------------------
	#-- Returns True if an event occured.
	#-------------------------------------------------------------------------------------
	def InputChanged( self ):
		return self.midi.ReadCheck()


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button or potentiometer change as a list:
	#-- potentiometers/sliders:  <pot.number>, <value>     , 0 ]
	#-- buttons:                 <pot.number>, <True/False>, 0 ]
	#-------------------------------------------------------------------------------------
	def InputStateRaw( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()
			
			#--- pressed
			if    a[0][0][0] == 144:
				return [ a[0][0][1], True, 127 ]
			#--- released
			elif  a[0][0][0] == 128:
				return [ a[0][0][1], False, 0 ]
			#--- potentiometers and the four cursor buttons
			elif  a[0][0][0] == 176:
				# --- cursor buttons
				if a[0][0][1] >= 104 and a[0][0][1] <= 107:
					if a[0][0][2] > 0:
						return [ a[0][0][1], True, a[0][0][2] ]
					else:
						return [ a[0][0][1], False, 0 ]
				# --- potentiometers
				else:
					return [ a[0][0][1], a[0][0][2], 0 ]
			else:
				return []
		else:
			return []



########################################################################################
### CLASS LaunchControl
###
### For 2-color Launch Control
########################################################################################
class LaunchControl( LaunchControlXL ):

	# LED, BUTTON AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
	#         
	#       0   1   2   3   4   5   6   7      8    9
	#      
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  0  | 21| 22| 23| 24| 25| 26| 27| 28|  |NOP||NOP| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  1  | 41| 42| 43| 44| 45| 46| 47| 48|  |114||115| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  2  |  9| 10| 11| 12| 25| 26| 27| 28|  |116||117| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#
	#
	# LED NUMBERS IN X/Y MODE (DEC)
	#
	#       0   1   2   3   4   5   6   7      8    9
	#      
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     | - | - | - | - | - | - | - | - |  |NOP||NOP| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  1  | - | - | - | - | - | - | - | - |  |8/1||9/1| 
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#     +---+---+---+---+---+---+---+---+  +---++---+
	#  0  |0/0|   |   |   |   |   |   |7/0|  |8/0||9/0| 
	#     +---+---+---+---+---+---+---+---+  +---++---+

	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Control MIDI devices.
	#-- Uses search string "Control MIDI", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchControlXL" method
	def Open( self, number = 0, name = "Control MIDI", template = 1 ):

		# The user template number adds to the MIDI commands.
		# Make sure that the Control is set to the corresponding mode by
		# holding down one of the template buttons and selecting the template
		# with the lowest button row 1..8 (variable here stores that as 0..7 for
		# user or 8..15 for the factory templates).
		# By default, user template 0 is enabled
		self.UserTemplate = template
		
		retval = super( LaunchControl, self ).Open( number = number, name = name )
		if retval == True:
			self.TemplateSet( self.UserTemplate )

		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "Control MIDI", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "Control MIDI" ):
		return super( LaunchControl, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Sets the layout template.
	#-- 1..8 selects the user and 9..16 the factory setups.
	#-------------------------------------------------------------------------------------
	def TemplateSet( self, templateNum ):
		if templateNum < 1 or templateNum > 16:
			return
		else:
			self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 10, 119, templateNum-1 ] )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its coordinates <x> and <y>  with <green/red> brightness 0..3
	#-- Actually, this doesn't make a lot of sense as the Control only has one row
	#-- of LEDs, but anyway ...
	#-------------------------------------------------------------------------------------
	def LedCtrlXY( self, x, y, red, green ):

		# TODO: Note about the y coords
		if x < 0 or x > 9 or y < 0 or y > 1:
			return

		if x < 8:
			color = self.LedGetColor( red, green )
		else:
			# the "special buttons" only have one color
			color = self.LedGetColor( 3, 3 )

		if y == 0:
#			index = [ 9, 10, 11, 12, 25, 26, 27, 28, 116, 117 ][x]
			index = [ 0, 1, 2, 3, 4, 5, 6, 7, 10, 11 ][x]
		else:
			if x == 8:
				index = 8
			elif x == 9:
				index = 9
			else:
				return

		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 10, 120, 0, index, color ] )



########################################################################################
### CLASS LaunchKey
###
### For 2-color LaunchKey Keyboards 
########################################################################################
class LaunchKeyMini( LaunchpadBase ):

	# LED, BUTTON, KEY AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
	# NOTICE THAT THE OCTAVE BUTTONS SHIFT THE KEYS UP OR DOWN BY 12.
	#
	# LAUNCHKEY MINI:
	# 
	#                   +---+---+---+---+---+---+---+---+
	#                   | 21| 22|...|   |   |   |   | 28|
	#     +---+---+---+ +---+---+---+---+---+---+---+---+ +---+  +---+
	#     |106|107|NOP| | 40| 41| 42| 43| 48| 49| 50| 51| |108|  |104| 
	#     +---+---+---+ +---+---+---+---+---+---+---+---+ +---+  +---+
	#     |NOP|NOP|     | 36| 37| 38| 39| 44| 45| 46| 47| |109|  |105| 
	#     +---+---+     +---+---+---+---+---+---+---+---+ +---+  +---+
	#
	#     +--+-+-+-+--+--+-+-+-+-+-+--+--+-+-+-+--+--+-+-+-+-+-+--+---+
	#     |  | | | |  |  | | | | | |  |  | | | |  |  | | | | | |  |   |
	#     |  |4| |5|  |  | | | | | |  |  |6| | |  |  | | | | |7|  |   |
	#     |  |9| |1|  |  | | | | | |  |  |1| | |  |  | | | | |0|  |   |
	#     |  +-+ +-+  |  +-+ +-+ +-+  |  +-+ +-+  |  +-+ +-+ +-+  |   |
	#     | 48| 50| 52|   |   |   |   | 60|   |   |   |   |   | 71| 72|
	#     |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
	#     | C | D | E |...|   |   |   | C2| D2|...|   |   |   |   | C3|
	#     +---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
	#
	#
	# LAUNCHKEY 25/49/61:
	#
	#    SLIDERS:           41..48
	#    SLIDER (MASTER):   7
	#
	


	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached LaunchKey devices.
	#-- Uses search string "LaunchKey", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Open( self, number = 0, name = "LaunchKey" ):
		retval = super( LaunchKeyMini, self ).Open( number = number, name = name )
		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "LaunchKey", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "LaunchKey" ):
		return super( LaunchKeyMini, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button, key or potentiometer change as a list:
	#-- potentiometers:   <pot.number>, <value>     , 0          ] 
	#-- buttons:          <but.number>, <True/False>, <velocity> ]
	#-- keys:             <but.number>, <True/False>, <velocity> ]
	#-- If a button does not provide an analog value, 0 or 127 are returned as velocity values.
	#-- Because of the octave settings cover the complete note range, the button and potentiometer
	#-- numbers collide with the note numbers in the lower octaves.
	#-------------------------------------------------------------------------------------
	def InputStateRaw( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()
			
			#--- pressed key
			if    a[0][0][0] == 144:
				return [ a[0][0][1], True, a[0][0][2] ] 
			#--- released key
			elif  a[0][0][0] == 128:
				return [ a[0][0][1], False, 0 ] 
			#--- pressed button
			elif  a[0][0][0] == 153:
				return [ a[0][0][1], True, a[0][0][2] ]
			#--- released button
			elif  a[0][0][0] == 137:
				return [ a[0][0][1], False, 0 ]
			#--- potentiometers and the four cursor buttons
			elif  a[0][0][0] == 176:
				# --- cursor, track and scene buttons
				if a[0][0][1] >= 104 and a[0][0][1] <= 109:
					if a[0][0][2] > 0:
						return [ a[0][0][1], True, 127 ]
					else:
						return [ a[0][0][1], False, 0 ]
				# --- potentiometers
				else:
					return [ a[0][0][1], a[0][0][2], 0 ]
			else:
				return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Clears the input buffer (The Launchpads remember everything...)
	#-------------------------------------------------------------------------------------
	def InputFlush( self ):
		return self.ButtonFlush()


	#-------------------------------------------------------------------------------------
	#-- Returns True if an event occured.
	#-------------------------------------------------------------------------------------
	def InputChanged( self ):
		return self.midi.ReadCheck()


########################################################################################
### CLASS Dicer
###
### For that Dicer thingy...
########################################################################################
class Dicer( LaunchpadBase ):

	# LED, BUTTON, KEY AND POTENTIOMETER NUMBERS IN RAW MODE (DEC)
	# NOTICE THAT THE OCTAVE BUTTONS SHIFT THE KEYS UP OR DOWN BY 10.
	#
	# FOR SHIFT MODE (HOLD ONE OF THE 3 MODE BUTTONS): ADD "5".
	#     +-----+  +-----+  +-----+             +-----+  +-----+  +-----+
	#     |#    |  |#    |  |     |             |#   #|  |#   #|  |    #|
	#     |  #  |  |     |  |  #  |             |  #  |  |     |  |  #  |
	#     |    #|  |    #|  |     |             |#   #|  |#   #|  |#    |
	#     +-----+  +-----+  +-----+             +-----+  +-----+  +-----+
	# 
	#     +-----+            +---+               +----+           +-----+
	#     |#   #|            | +0|               |+120|           |    #|
	#     |     |            +---+               +----+           |     |
	#     |#   #|       +---+                         +----+      |#    |
	#     +-----+       |+10|                         |+110|      +-----+
	#                   +---+                         +----+
	#     +-----+  +---+                                  +----+  +-----+
	#     |#   #|  |+20|                                  |+100|  |     |
	#     |  #  |  +---+                                  +----+  |  #  |
	#     |#   #|                                                 |     |
	#     +-----+                                                 +-----+
	# 
	# 


	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Dicer devices.
	#-- Uses search string "dicer", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Open( self, number = 0, name = "Dicer" ):
		retval = super( Dicer, self ).Open( number = number, name = name )
		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "dicer", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "Dicer" ):
		return super( Dicer, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- reset the Dicer
	#-- Turns off all LEDs, restores power-on state, but does not disable an active light show.
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.midi.RawWrite( 186, 0, 0 )


	#-------------------------------------------------------------------------------------
	#-- All LEDs off
	#-- Turns off all LEDs, does not change or touch any other settings.
	#-------------------------------------------------------------------------------------
	def LedAllOff( self ):
		self.midi.RawWrite( 186, 0, 112 )


	#-------------------------------------------------------------------------------------
	#-- Returns (an already nicely mapped and not raw :) value of the last button change as a list:
	#-- buttons: <number>, <True/False>, <velocity> ]
	#-- If a button does not provide an analog value, 0 or 127 are returned as velocity values.
	#-- Small buttons select either 154, 155, 156 cmd for master or 157, 158, 159 for slave.
	#-- Button numbers (1 to 5): 60, 61 .. 64; always
	#-- Guess it's best to return: 1..5, 11..15, 21..25 for Master and 101..105, ... etc for slave
	#-- Actually, as you can see, it's not "raw", but I guess those decade modifiers really
	#-- make sense here (less brain calculations for you :)
	#-------------------------------------------------------------------------------------
	def ButtonStateRaw( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()
			
			#--- button on master
			if   a[0][0][0] >= 154 and a[0][0][0] <= 156:
				butNum = a[0][0][1]
				if butNum >= 60 and butNum <= 69:
					butNum -= 59
					butNum += 10 * ( a[0][0][0]-154 )
					if a[0][0][2] == 127:
						return [ butNum, True, 127 ]
					else:
						return [ butNum, False, 0  ]
				else:
					return []
			#--- button on master
			elif a[0][0][0] >= 157 and a[0][0][0] <= 159:
				butNum = a[0][0][1]
				if butNum >= 60 and butNum <= 69:
					butNum -= 59
					butNum += 100 + 10 * ( a[0][0][0]-157 )
					if a[0][0][2] == 127:
						return [ butNum, True, 127 ]
					else:
						return [ butNum, False, 0  ]
				else:
					return []
		else:
			return []

	#-------------------------------------------------------------------------------------
	#-- Enables or diabled the Dicer's built-in light show.
	#-- Device: 0 = Master, 1 = Slave; enable = True/False
	#-------------------------------------------------------------------------------------
	def LedSetLightshow( self, device, enable ):
		# Who needs error checks anyway?
		self.midi.RawWrite( 186 if device == 0 else 189, 0, 40 if enable == True else 41 )


	#-------------------------------------------------------------------------------------
	#-- Returns a Dicer compatible "color code byte"
	#-- NOTE: Copied from Launchpad, won't work. The Dicer actually uses:
	#-- Byte: 0b[0HHHIIII]; HHH: 3 bits hue (000=red up to 111=green) and 4 bits IIII as intensity.
	#-------------------------------------------------------------------------------------
#	def LedGetColor( self, red, green ):
#		led = 0
#		
#		red = min( int(red), 3 ) # make int and limit to <=3
#		red = max( red, 0 )      # no negative numbers
#
#		green = min( int(green), 3 ) # make int and limit to <=3
#		green = max( green, 0 )      # no negative numbers
#
#		led |= red
#		led |= green << 4 
#		
#		return led


	#-------------------------------------------------------------------------------------
	#-- Controls an LED by its raw <number>; with <hue> brightness: 0..7 (red to green)
	#-- and <intensity> 0..15
	#-- For LED numbers, see grid description on top of class.
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, hue, intensity ):
		
		if number < 0 or number > 130:
			return
		
		# check if that is a slave device number (>100)
		if number > 100:
			number -= 100
			cmd = 157
		else:
			cmd = 154
			
		# determine the "page", "hot cue", "loop" or "auto loop"
		page = number // 10
		if page > 2:
			return

		# correct the "page shifted" LED number
		number = number - ( page * 10 )
		if number > 10:
			return
		
		# limit the hue range
		hue = min( int(hue), 7 ) # make int and limit to <=7
		hue = max( hue, 0 )      # no negative numbers

		# limit the intensity
		intensity = min( int(intensity), 15 ) # make int and limit to <=15
		intensity = max( intensity, 0 )       # no negative numbers
		
		self.midi.RawWrite( cmd + page, number + 59, (hue << 4) | intensity )


	#-------------------------------------------------------------------------------------
	#-- Sets the Dicer <device> (0=master, 1=slave) to one of its six modes,
	#-- as specified by <mode>:
	#--  0 - "cue"
	#--  1 - "cue, shift lock"
	#--  2 - "loop"
	#--  3 - "loop, shift lock"
	#--  4 - "auto loop"
	#--  5 - "auto loop, shift lock"
	#--  6 - "one page"
	#-------------------------------------------------------------------------------------
	def ModeSet( self, device, mode ):

		if device < 0 or device > 1:
			return

		if mode < 0 or mode > 6:
			return

		self.midi.RawWrite( 186 if device == 0 else 189, 17, mode )



########################################################################################
### CLASS LaunchpadMiniMk3
###
### For 3-color "Mk3" Launchpads; Mini and Pro
########################################################################################
class LaunchpadMiniMk3( LaunchpadPro ):

	# LED AND BUTTON NUMBERS IN RAW MODE (DEC)
	#
	#
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |104|   |106|   |   |   |   |111|  |112|
	#        +---+---+---+---+---+---+---+---+  +---+
	#         
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 81|   |   |   |   |   |   |   |  | 89|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 71|   |   |   |   |   |   |   |  | 79|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 61|   |   |   |   |   | 67|   |  | 69|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 51|   |   |   |   |   |   |   |  | 59|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 41|   |   |   |   |   |   |   |  | 49|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 31|   |   |   |   |   |   |   |  | 39|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 21|   | 23|   |   |   |   |   |  | 29|
	#        +---+---+---+---+---+---+---+---+  +---+
	#        | 11|   |   |   |   |   |   |   |  | 19|
	#        +---+---+---+---+---+---+---+---+  +---+
	#       
	#
	#
	# LED AND BUTTON NUMBERS IN XY MODE (X/Y)
	#
	#          0   1   2   3   4   5   6   7      8   
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |0/0|   |2/0|   |   |   |   |   |  |8/0|  0
	#        +---+---+---+---+---+---+---+---+  +---+
	#         
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |0/1|   |   |   |   |   |   |   |  |   |  1
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  2
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |5/3|   |   |  |   |  3
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  4
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  5
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |4/6|   |   |   |  |   |  6
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |   |  7
	#        +---+---+---+---+---+---+---+---+  +---+
	#        |   |   |   |   |   |   |   |   |  |8/8|  8
	#        +---+---+---+---+---+---+---+---+  +---+
	#       


#	COLORS = {'black':0, 'off':0, 'white':3, 'red':5, 'green':17 }

	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-- Uses search string "MiniMk3", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def Open( self, number = 0, name = "MiniMK3" ):
		retval = super( LaunchpadMiniMk3, self ).Open( number = number, name = name )
		if retval == True:
			self.LedSetMode( 1 )

		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "MiniMk3", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "MiniMK3" ):
		return super( LaunchpadMiniMk3, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Sets the button layout (and codes) to the set, specified by <mode>.
	#-- Valid options:
	#--  00 - Session, 04 - Drums, 05 - Keys, 06 - User (Drum)
	#--  0D - DAW Faders (available if Session enabled), 7F - Programmer
	#-- Until now, we'll need the "Session" (0x00) settings.
	#-------------------------------------------------------------------------------------
	# TODO: ASkr, Undocumented!
	# TODO: return value
	def LedSetLayout( self, mode ):
		ValidModes = [0x00, 0x04, 0x05, 0x06, 0x0d, 0x7F]
		if mode not in ValidModes:
			return
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 13, 0, mode ] )
		time.wait(10)


	#-------------------------------------------------------------------------------------
	#-- Selects the Mk3's mode.
	#-- <mode> -> 0 -> "Ableton Live mode"  
	#--           1 -> "Programmer mode"	(what we need)
	#-------------------------------------------------------------------------------------
	def LedSetMode( self, mode ):
		if mode < 0 or mode > 1:
			return
			
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 13, 14, mode ] )
		time.wait(10)


	#-------------------------------------------------------------------------------------
	#-- Sets the button layout to "Session" mode.
	#-------------------------------------------------------------------------------------
	# TODO: ASkr, Undocumented!
	def LedSetButtonLayoutSession( self ):
		self.LedSetLayout( 0 )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color, specified by
	#-- <red>, <green> and <blue> intensities, with can each be an integer between 0..63.
	#-- If <blue> is omitted, this methos runs in "Classic" compatibility mode and the
	#-- intensities, which were within 0..3 in that mode, are multiplied by 21 (0..63)
	#-- to emulate the old brightness feeling :)
	#-- Notice that each message requires 10 bytes to be sent. For a faster, but
	#-- unfortunately "not-RGB" method, see "LedCtrlRawByCode()"
	#-- Mk3 color data extended to 7-bit but for compatibility we still using 6-bit values
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, red, green, blue = None ):

		if number < 0 or number > 99:
			return

		if blue is None:
			blue   = 0
			red   *= 21
			green *= 21
		
		limit = lambda n, mini, maxi: max(min(maxi, n), mini)
		
		red   = limit( red,   0, 63 ) << 1
		green = limit( green, 0, 63 ) << 1
		blue  = limit( blue,  0, 63 ) << 1
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 13, 3, 3, number, red, green, blue ] )
	

	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlRawByCode, but with a pulsing LED.
	#-- Pulsing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlPulseByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		colorcode = min(127, max(0, colorcode))

		self.midi.RawWrite( 146, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlPulseByCode, but with a dual color flashing LED.
	#-- The first color is the one that is already enabled, the second one is the
	#-- <colorcode> argument in this method.
	#-- Flashing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlFlashByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		colorcode = min(127, max(0, colorcode))

		self.midi.RawWrite( 145, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Quickly sets all all LEDs to the same color, given by <colorcode>.
	#-- If <colorcode> is omitted, "white" is used.
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']
		
		colorcode = min(127, max(0, colorcode))

		# TODO: Maybe the SysEx was indeed a better idea :)
		#       Did some tests:
		#         MacOS:   doesn't matter;
		#         Windoze: SysEx much better;
		#         Linux:   completely freaks out
		for x in range(9):
			for y in range(9):
				self.midi.RawWrite(144, (x + 1) + ((y + 1) * 10), colorcode)


	#-------------------------------------------------------------------------------------
	#-- (fake to) reset the Launchpad
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.LedAllOn( 0 )


	#-------------------------------------------------------------------------------------
	#-- Go back to custom modes before closing connection
	#-- Otherwise Launchpad will stuck in programmer mode
	#-------------------------------------------------------------------------------------
	def Close( self ):
		# removed for now (LEDs would light up again; should be in the user's code)
#		self.LedSetLayout( 0x05 )

		# TODO: redundant (but needs fix for Py2 embedded anyway)
		self.midi.CloseInput()
		self.midi.CloseOutput()


########################################################################################
### CLASS LaunchpadLPX
###
### For 3-color "X" Launchpads
########################################################################################
class LaunchpadLPX( LaunchpadPro ):
	
#	COLORS = {'black':0, 'off':0, 'white':3, 'red':5, 'green':17 }

	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-- This is one of the few devices that has different names in different OSs:
	#--
	#--   Windoze
	#--     (b'MMSystem', b'LPX MIDI', 1, 0, 0)
	#--     (b'MMSystem', b'MIDIIN2 (LPX MIDI)', 1, 0, 0)
	#--     (b'MMSystem', b'LPX MIDI', 0, 1, 0)
	#--     (b'MMSystem', b'MIDIOUT2 (LPX MIDI)', 0, 1, 0)
	#--   
	#--   macOS
	#--     (b'CoreMIDI', b'Launchpad X LPX DAW Out', 1, 0, 0)
	#--     (b'CoreMIDI', b'Launchpad X LPX MIDI Out', 1, 0, 0)
	#--     (b'CoreMIDI', b'Launchpad X LPX DAW In', 0, 1, 0)
	#--     (b'CoreMIDI', b'Launchpad X LPX MIDI In', 0, 1, 0)
	#--   
	#--   Linux [tm]
	#--     ('ALSA', 'Launchpad X MIDI 1', 0, 1, 0)
	#--     ('ALSA', 'Launchpad X MIDI 1', 1, 0, 0)
	#--     ('ALSA', 'Launchpad X MIDI 2', 0, 1, 0)
	#--     ('ALSA', 'Launchpad X MIDI 2', 1, 0, 0)
	#--
	#-- So the old strategy of simply looking for "LPX" will not work.
	#-- Workaround: If the user doesn't request a specific name, we'll just
	#-- search for "Launchpad X" and "LPX"...
	
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def Open( self, number = 0, name = "AUTO" ):
		nameList = [ "Launchpad X", "LPX" ]
		if name != "AUTO":
			# mhh, better not this way
			# nameList.insert( 0, name )
			nameList = [ name ]
		for name in nameList:
			rval = super( LaunchpadLPX, self ).Open( number = number, name = name )
			if rval:
				self.LedSetMode( 1 )
				return rval
		return False


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- See notes in "Open()" above.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "AUTO" ):
		nameList = [ "Launchpad X", "LPX" ]
		if name != "AUTO":
			# mhh, better not this way
			# nameList.insert( 0, name )
			nameList = [ name ]
		for name in nameList:
			rval = super( LaunchpadLPX, self ).Check( number = number, name = name )
			if rval:
				return rval
		return False


	#-------------------------------------------------------------------------------------
	#-- Sets the button layout (and codes) to the set, specified by <mode>.
	#-- Valid options:
	#--  00 - Session, 01 - Note Mode, 04 - Custom 1, 05 - Custom 2, 06 - Custom 3
	#--  07 - Custom 4, 0D - DAW Faders (available if Session enabled), 7F - Programmer
	#-------------------------------------------------------------------------------------
	# TODO: ASkr, Undocumented!
	# TODO: return value
	def LedSetLayout( self, mode ):
		ValidModes = [0x00, 0x01, 0x04, 0x05, 0x06, 0x07, 0x0d, 0x7F]
		if mode not in ValidModes:
			return
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 12, 0, mode ] )
		time.wait(10)


	#-------------------------------------------------------------------------------------
	#-- Selects the LPX's mode.
	#-- <mode> -> 0 -> "Ableton Live mode"  
	#--           1 -> "Programmer mode"	(what we need)
	#-------------------------------------------------------------------------------------
	def LedSetMode( self, mode ):
		if mode < 0 or mode > 1:
			return
			
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 12, 14, mode ] )
		time.wait(10)


	#-------------------------------------------------------------------------------------
	#-- Sets the button layout to "Session" mode.
	#-------------------------------------------------------------------------------------
	# TODO: ASkr, Undocumented!
	def LedSetButtonLayoutSession( self ):
		self.LedSetLayout( 0 )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color, specified by
	#-- <red>, <green> and <blue> intensities, with can each be an integer between 0..63.
	#-- If <blue> is omitted, this methos runs in "Classic" compatibility mode and the
	#-- intensities, which were within 0..3 in that mode, are multiplied by 21 (0..63)
	#-- to emulate the old brightness feeling :)
	#-- Notice that each message requires 10 bytes to be sent. For a faster, but
	#-- unfortunately "not-RGB" method, see "LedCtrlRawByCode()"
	#-- LPX color data extended to 7-bit but for compatibility we still using 6-bit values
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, red, green, blue = None ):

		if number < 0 or number > 99:
			return

		if blue is None:
			blue   = 0
			red   *= 21
			green *= 21
		
		limit = lambda n, mini, maxi: max(min(maxi, n), mini)
		
		red   = limit( red,   0, 63 ) << 1
		green = limit( green, 0, 63 ) << 1
		blue  = limit( blue,  0, 63 ) << 1
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 12, 3, 3, number, red, green, blue ] )
	

	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlRawByCode, but with a pulsing LED.
	#-- Pulsing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlPulseByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		colorcode = min(127, max(0, colorcode))

		self.midi.RawWrite( 146, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlPulseByCode, but with a dual color flashing LED.
	#-- The first color is the one that is already enabled, the second one is the
	#-- <colorcode> argument in this method.
	#-- Flashing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlFlashByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		colorcode = min(127, max(0, colorcode))

		self.midi.RawWrite( 145, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Quickly sets all all LEDs to the same color, given by <colorcode>.
	#-- If <colorcode> is omitted, "white" is used.
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']
		
		colorcode = min(127, max(0, colorcode))

		# TODO: Maybe the SysEx was indeed a better idea :)
		#       Did some tests:
		#         MacOS:   doesn't matter;
		#         Windoze: SysEx much better;
		#         Linux:   completely freaks out
		for x in range(9):
			for y in range(9):
				self.midi.RawWrite(144, (x + 1) + ((y + 1) * 10), colorcode)


	#-------------------------------------------------------------------------------------
	#-- (fake to) reset the Launchpad
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.LedAllOn( 0 )


	#-------------------------------------------------------------------------------------
	#-- Go back to custom modes before closing connection
	#-- Otherwise Launchpad will stuck in programmer mode
	#-------------------------------------------------------------------------------------
	def Close( self ):
		# TODO: redundant (but needs fix for Py2 embedded anyway)
		self.midi.CloseInput()
		self.midi.CloseOutput()


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <button>, <value> ], in which <button> is the raw number of the button and
	#-- <value> an intensity value from 0..127.
	#-- >0 = button pressed; 0 = button released
	#-- Notice that this is not (directly) compatible with the original ButtonStateRaw()
	#-- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
	#-- Compatibility would require checking via "== True" and not "is True".
	#-- Pressure events are returned if enabled via "returnPressure". 
	#-- Unlike the Launchpad Pro, the X does indeed return the button number AND the
	#-- pressure value. To provide visibility whether or not a button was pressed or is
	#-- hold, a value of 255 is added to the button number.
	#-- [ <button> + 255, <value> ].
	#-- In contrast to the Pro, which only has one pressure value for all, the X does
	#-- this per button. Nice.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def ButtonStateRaw( self, returnPressure = False ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			# Copied over from the Pro's method.
			# Try to avoid getting flooded with pressure events
			if returnPressure == False:
				while a[0][0][0] == 160:
					a = self.midi.ReadRaw()
					if a == []:
						return []

			if a[0][0][0] == 144 or a[0][0][0] == 176:
				return [ a[0][0][1], a[0][0][2] ]
			else:
				if returnPressure:
					if a[0][0][0] == 160:
						# the X returns button number AND pressure value
						# adding 255 to make it possible to distinguish "pressed" from "pressure"
						return [ 255 + a[0][0][1], a[0][0][2] ]
					else:
						return []
				else:
					return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
	#-- <value> is the intensity from 0..127.
	#-- >0 = button pressed; 0 = button released
	#-- Notice that this is not (directly) compatible with the original ButtonStateRaw()
	#-- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
	#-- Compatibility would require checking via "== True" and not "is True".
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def ButtonStateXY( self, mode = "classic", returnPressure = False ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			# 8/2020: Copied from the Pro.
			# 9/2020: now also _with_ pressure :)
			if returnPressure == False:
				while a[0][0][0] == 160:
					a = self.midi.ReadRaw()
					if a == []:
						return []

			if a[0][0][0] == 144 or a[0][0][0] == 176 or a[0][0][0] == 160:
			
				if mode.lower() != "pro":
					x = (a[0][0][1] - 1) % 10
				else:
					x = a[0][0][1] % 10
				y = ( 99 - a[0][0][1] ) // 10

				# now with pressure events (9/2020)
				if a[0][0][0] == 160 and returnPressure == True:
					return [ x+255, y+255, a[0][0][2] ]
				else:
					return [ x, y, a[0][0][2] ]
			else:
					return []
		else:
			return []


########################################################################################
### CLASS MidiFighter64
###
### For Midi Fighter 64 Gedöns
########################################################################################
class MidiFighter64( LaunchpadBase ):

	#         
	# LED AND BUTTON NUMBERS IN RAW MODE
	#         
	#        +---+---+---+---+---+---+---+---+
	#        | 64|   |   | 67| 96|   |   | 99|
	#        +---+---+---+---+---+---+---+---+
	#        | 60|   |   | 63| 92|   |   | 95|
	#        +---+---+---+---+---+---+---+---+
	#        | 56|   |   | 59| 88|   |   | 91|
	#        +---+---+---+---+---+---+---+---+
	#        | 52|   |   | 55| 84|   |   | 87|
	#        +---+---+---+---+---+---+---+---+
	#        | 48|   |   | 51| 80|   |   | 83|
	#        +---+---+---+---+---+---+---+---+
	#        | 44|   |   | 47| 76|   |   | 79|
	#        +---+---+---+---+---+---+---+---+
	#        | 40|   |   | 43| 72|   |   | 75|
	#        +---+---+---+---+---+---+---+---+
	#        | 36|   |   | 39| 68|   |   | 71|
	#        +---+---+---+---+---+---+---+---+
	#
	#
	# LED AND BUTTON NUMBERS IN XY MODE (X/Y)
	#
	#          0   1   2   3   4   5   6   7
	#        +---+---+---+---+---+---+---+---+
	#        |0/0|   |   |   |   |   |   |   | 0
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |   |   |   |   | 1
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |   |5/2|   |   | 2
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |   |   |   |   | 3
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |   |   |   |   | 4
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |4/5|   |   |   | 5
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |   |   |   |   | 6
	#        +---+---+---+---+---+---+---+---+
	#        |   |   |   |   |   |   |   |   | 7
	#        +---+---+---+---+---+---+---+---+
	#


	#-------------------------------------------------------------------------------------
	#-- Add some LED mode "constants" for better usability.
	#-------------------------------------------------------------------------------------
	def __init__( self ):

		self.MODE_BRIGHT        = [ i+18 for i in range(16) ]
		self.MODE_TOGGLE        = [ i+34 for i in range(8) ]
		self.MODE_PULSE         = [ i+42 for i in range(8) ]
		self.MODE_ANIM_SQUARE   = 50
		self.MODE_ANIM_CIRCLE   = 51
		self.MODE_ANIM_STAR     = 52
		self.MODE_ANIM_TRIANGLE = 53

		super( MidiFighter64, self ).__init__( )



	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-- Uses search string "Fighter 64", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Open( self, number = 0, name = "Fighter 64" ):
		return super( MidiFighter64, self ).Open( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "Fighter 64", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadBase" method
	def Check( self, number = 0, name = "Fighter 64" ):
		return super( MidiFighter64, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its <number> and a <color>.
	#--  <number> 36..99
	#--  <color>   0..127 from color table
	#--  <mode>   18..53  for brightness, toggling and animation 
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, color, mode = None ):

		if number < 36 or number > 99:
			return
		if color  < 0  or color  > 127:
			return

		self.midi.RawWrite( 146, number, color )

		# faster than calling LedCtrlRawMode()
		if mode is not None and mode > 17 and mode < 54:
			self.midi.RawWrite( 147, number - 3*12, mode )


	#-------------------------------------------------------------------------------------
	#-- Controls a the mode of a grid LED by its <number> and the mode <mode> of the LED.
	#--  <number> 36..99
	#--  <mode>   18..53 for brightness, toggling and animation
	#-- Internal LED numbers are 3 octaves lower than the color numbers.
	#-- The mode must be sent over channel 4
	#-------------------------------------------------------------------------------------
	def LedCtrlRawMode( self, number, mode ):

		# uses the original button numbers for usability
		if number < 36 or number > 99:
			return
		if mode < 18 or mode > 53:
			return

		self.midi.RawWrite( 147, number - 3*12, mode )


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its <x>/<y> coordinates and a <color>.
	#--  <x>/<y>  0..7
	#--  <color>  0..127 from color table
	#-------------------------------------------------------------------------------------
	def LedCtrlXY( self, x, y, color, mode = None ):

		if x < 0 or x > 7:
			return
		if y < 0 or y > 7:
			return
		if color  < 0  or color  > 127:
			return

		if x < 4:
			number = 36 + x % 4
		else:
			number = 68 + x % 4
		
		number += (7-y) * 4

		self.midi.RawWrite( 146, number, color )
		# set the mode if required; faster than calling LedCtrlRawMode()
		if mode is not None and mode > 17 and mode < 54:
			self.midi.RawWrite( 147, number - 3*12, mode )


	#-------------------------------------------------------------------------------------
	#-- Displays the character <char> with color of <colorcode> and lateral offset
	#-- <offsx> (-8..8) on the Midi Fighter. <offsy> does not have yet any function.
	#-- <coloroff> specifies the background color.
	#-- Notice that the call to this method is not compatible to the Launchpad variants,
	#-- because the Midi Fighter lacks support for RGB.
	#-------------------------------------------------------------------------------------
	def LedCtrlChar( self, char, colorcode, offsx = 0, offsy = 0, coloroff = 0 ):
		char = ord( char )
		char = min( char, 255)
		char = max( char, 0) * 8

		if colorcode < 0 or colorcode > 127:
			return

		for y in range( 64, 35, -4 ):
			for x in range(8):
				number = y + x + offsx
				if x + offsx > 3:
					number += 28  # +32-4

				if x + offsx < 8 and x + offsx >= 0:
					if CHARTAB[char]  &  0x80 >> x:
						self.LedCtrlRaw( number, colorcode )
					else:
						# lol, shit; there is no color code for "off"
						self.LedCtrlRaw( number, coloroff )
			char += 1


	#-------------------------------------------------------------------------------------
	#-- Scroll <text>, with color specified by <colorcode>, as fast as we can.
	#-- <direction> specifies: -1 to left, 0 no scroll, 1 to right
	#-- Notice that the call to this method is not compatible to the Launchpad variants,
	#-- because the Midi Fighter lacks support for RGB.
	#-------------------------------------------------------------------------------------
	def LedCtrlString( self, text, colorcode, coloroff=0, direction = None, waitms = 150 ):

		limit = lambda n, mini, maxi: max(min(maxi, n), mini)

		if direction == self.SCROLL_LEFT:
			text += " " # just to avoid artifacts on full width characters
			for n in range( (len(text) + 1) * 8 ):
				if n <= len(text)*8:
					self.LedCtrlChar( text[ limit( (  n   //16)*2     , 0, len(text)-1 ) ], colorcode, 8- n   %16, coloroff = coloroff )
				if n > 7:
					self.LedCtrlChar( text[ limit( (((n-8)//16)*2) + 1, 0, len(text)-1 ) ], colorcode, 8-(n-8)%16, coloroff = coloroff )
				time.wait(waitms)
		elif direction == self.SCROLL_RIGHT:
			# TODO: Just a quick hack (screen is erased before scrolling begins).
			#       Characters at odd positions from the right (1, 3, 5), with pixels at the left,
			#       e.g. 'C' will have artifacts at the left (pixel repeated).
			text = " " + text + " " # just to avoid artifacts on full width characters
#			for n in range( (len(text) + 1) * 8 - 1, 0, -1 ):
			for n in range( (len(text) + 1) * 8 - 7, 0, -1 ):
				if n <= len(text)*8:
					self.LedCtrlChar( text[ limit( (  n   //16)*2     , 0, len(text)-1 ) ], colorcode, 8- n   %16, coloroff = coloroff )
				if n > 7:
					self.LedCtrlChar( text[ limit( (((n-8)//16)*2) + 1, 0, len(text)-1 ) ], colorcode, 8-(n-8)%16, coloroff = coloroff )
				time.wait(waitms)
		else:
			for i in text:
				for n in range(4):  # pseudo repetitions to compensate the timing a bit
					self.LedCtrlChar(i, colorcode, coloroff = coloroff)
					time.wait(waitms)


	#-------------------------------------------------------------------------------------
	#-- Sets all LEDs to the same color, specified by <color>.
	#-- If color is omitted, the LEDs are set to white (code 3)
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, color = 3, mode = None ):
		for i in range(64):
			self.LedCtrlRaw( i+36, color, mode )


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <button>, <velocity> ], in which <button> is the raw number of the button and
	#-- <velocity> the button state.
	#--   >0 = button pressed; 0 = button released
	#-------------------------------------------------------------------------------------
	def ButtonStateRaw( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			# The Midi Fighter 64 does not support velocities. For 500 bucks. Lol :'-)
			# What we see here are either channel 3 or 2 NoteOn/NoteOff commands,
			# the factory settings, depending on the "bank selection".
			#   Channel 3 -> hold upper left  button for longer than 2s
			#   Channel 2 -> hold upper right button for longer than 2s
			#
			#    [[[146, 81, 127, 0], 47365]]
			#    [[[130, 81, 127, 0], 47443]]
			#    [[[146, 82, 127, 0], 47610]]
			#
			#    [[[ <NoteOn/Off>, <button>, 127, 0], 47610]]
			#
			#    146/145 -> NoteOn
			#    130/129 -> NoteOff
			#    127     -> fixed velocity (as set by the Midi Fighter utility )

			# Mhh, I guess it's about time to think about adding MIDI channels, isn't it?
			# But for now, we just check ch 2 and 3:
			if a[0][0][0] == 145 or a[0][0][0] == 146:
				return [ a[0][0][1], a[0][0][2] ]
			else:
				if a[0][0][0] == 130 or a[0][0][0] == 129:
					return [ a[0][0][1], 0 ]
				else:
					return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <x>, <y>, <velocity> ], in which <x>/<y> are the coordinates of the grid and
	#-- <velocity> the state of the button.
	#--   >0 = button pressed; 0 = button released
	#-------------------------------------------------------------------------------------
	def ButtonStateXY( self ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			# whatever that is, does not belong here...
			if a[0][0][1] < 36 or a[0][0][1] > 99:
				return []

			x = (a[0][0][1] - 36) % 4
			if a[0][0][1] >= 68:
				x += 4
			y = 7 - ( (a[0][0][1] - 36) % 32 ) // 4

			if a[0][0][0] == 145 or a[0][0][0] == 146:
				return [ x, y, a[0][0][2] ]
			else:
				if a[0][0][0] == 130 or a[0][0][0] == 129:
					return [ x, y, 0 ]
				else:
					return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- Reset the Midi Fighter
	#-- Well, at least turn off all its LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		# TODO
		# self.LedAllOn( 0 ) 
		pass



########################################################################################
### CLASS LaunchpadPROMk3
###
### For 3-color Pro Mk3 Launchpads
########################################################################################
class LaunchpadProMk3( LaunchpadPro ):
	#
	# LED AND BUTTON NUMBERS IN RAW MODE
	#
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 90|  | 91|   |   |   |   |   |   | 98|  | 99|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#         
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 80|  | 81|   |   |   |   |   |   |   |  | 89|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 70|  |   |   |   |   |   |   |   |   |  | 79|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 60|  |   |   |   |   |   |   | 67|   |  | 69|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 50|  |   |   |   |   |   |   |   |   |  | 59|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 40|  |   |   |   |   |   |   |   |   |  | 49|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 30|  |   |   |   |   |   |   |   |   |  | 39|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 20|  |   |   | 23|   |   |   |   |   |  | 29|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# | 10|  |   |   |   |   |   |   |   |   |  | 19|
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#       
	#        +---+---+---+---+---+---+---+---+ 
	#        |101|102|   |   |   |   |   |108|
	#        +---+---+---+---+---+---+---+---+ 
	#        |  1|  2|   |   |   |   |   |  8|
	#        +---+---+---+---+---+---+---+---+ 
	#
	#
	# LED AND BUTTON NUMBERS IN XY CLASSIC MODE (X/Y)
	#
	#   9      0   1   2   3   4   5   6   7      8   
	#        +---+---+---+---+---+---+---+---+ 
	#        |0/0|   |2/0|   |   |   |   |   |         0
	#        +---+---+---+---+---+---+---+---+ 
	#         
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |0/1|   |   |   |   |   |   |   |  |   |  1
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |9/2|  |   |   |   |   |   |   |   |   |  |   |  2
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |5/3|   |   |  |   |  3
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  4
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  5
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |4/6|   |   |   |  |   |  6
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  7
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |9/8|  |   |   |   |   |   |   |   |   |  |8/8|  8
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#       
	#        +---+---+---+---+---+---+---+---+ 
	#        |   |1/9|   |   |   |   |   |   |         9
	#        +---+---+---+---+---+---+---+---+ 
	#        |/10|   |   |   |   |   |   |   |        10
	#        +---+---+---+---+---+---+---+---+ 
	#
	#
	# LED AND BUTTON NUMBERS IN XY PRO MODE (X/Y)
	#
	#   0      1   2   3   4   5   6   7   8      9
	#        +---+---+---+---+---+---+---+---+ 
	#        |1/0|   |3/0|   |   |   |   |   |         0
	#        +---+---+---+---+---+---+---+---+ 
	#         
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |1/1|   |   |   |   |   |   |   |  |   |  1
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |0/2|  |   |   |   |   |   |   |   |   |  |   |  2
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |6/3|   |   |  |   |  3
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  4
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  5
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |5/6|   |   |   |  |   |  6
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |   |  |   |   |   |   |   |   |   |   |  |   |  7
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	# |0/8|  |   |   |   |   |   |   |   |   |  |9/8|  8
	# +---+  +---+---+---+---+---+---+---+---+  +---+
	#       
	#        +---+---+---+---+---+---+---+---+ 
	#        |   |2/9|   |   |   |   |   |8/9|         9
	#        +---+---+---+---+---+---+---+---+ 
	#        |   |   |   |   |   |   |   |/10|        10
	#        +---+---+---+---+---+---+---+---+ 

	
	#-------------------------------------------------------------------------------------
	#-- Opens one of the attached Launchpad MIDI devices.
	#-- Uses search string "ProMK3", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def Open( self, number = 0, name = "ProMk3" ):
		retval = super( LaunchpadProMk3, self ).Open( number = number, name = name )
		if retval == True:
			# enable Programmer's mode
			self.LedSetMode( 1 )
		return retval


	#-------------------------------------------------------------------------------------
	#-- Checks if a device exists, but does not open it.
	#-- Does not check whether a device is in use or other, strange things...
	#-- Uses search string "ProMk3", by default.
	#-------------------------------------------------------------------------------------
	# Overrides "LaunchpadPro" method
	def Check( self, number = 0, name = "ProMk3" ):
		return super( LaunchpadProMk3, self ).Check( number = number, name = name )


	#-------------------------------------------------------------------------------------
	#-- Selects the ProMk3's mode.
	#-- <mode> -> 0 -> "Ableton Live mode"  
	#--           1 -> "Programmer mode"	(what we need)
	#-------------------------------------------------------------------------------------
	def LedSetMode( self, mode ):
		if mode < 0 or mode > 1:
			return
			
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 14, 14, mode ] )
		time.wait(100)


	#-------------------------------------------------------------------------------------
	#-- Controls a grid LED by its position <number> and a color, specified by
	#-- <red>, <green> and <blue> intensities, with can each be an integer between 0..63.
	#-- If <blue> is omitted, this methos runs in "Classic" compatibility mode and the
	#-- intensities, which were within 0..3 in that mode, are multiplied by 21 (0..63)
	#-- to emulate the old brightness feeling :)
	#-- Notice that each message requires 10 bytes to be sent. For a faster, but
	#-- unfortunately "not-RGB" method, see "LedCtrlRawByCode()"
	#-- ProMk3 color data extended to 7-bit but for compatibility we still using 6-bit values
	#-------------------------------------------------------------------------------------
	def LedCtrlRaw( self, number, red, green, blue = None ):

		if number < 0 or number > 99:
			return

		if blue is None:
			blue   = 0
			red   *= 21
			green *= 21
		
		limit = lambda n, mini, maxi: max(min(maxi, n), mini)
		
		red   = limit( red,   0, 63 ) << 1
		green = limit( green, 0, 63 ) << 1
		blue  = limit( blue,  0, 63 ) << 1
		
		self.midi.RawWriteSysEx( [ 0, 32, 41, 2, 14, 3, 3, number, red, green, blue ] )
	

	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlRawByCode, but with a pulsing LED.
	#-- Pulsing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlPulseByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		colorcode = min(127, max(0, colorcode))

		self.midi.RawWrite( 146, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Same as LedCtrlPulseByCode, but with a dual color flashing LED.
	#-- The first color is the one that is already enabled, the second one is the
	#-- <colorcode> argument in this method.
	#-- Flashing can be stoppped by another Note-On/Off or SysEx message.
	#-------------------------------------------------------------------------------------
	def LedCtrlFlashByCode( self, number, colorcode = None ):

		if number < 0 or number > 99:
			return

		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']

		colorcode = min(127, max(0, colorcode))

		self.midi.RawWrite( 145, number, colorcode )


	#-------------------------------------------------------------------------------------
	#-- Quickly sets all all LEDs to the same color, given by <colorcode>.
	#-- If <colorcode> is omitted, "white" is used.
	#-------------------------------------------------------------------------------------
	def LedAllOn( self, colorcode = None ):
		if colorcode is None:
			colorcode = LaunchpadPro.COLORS['white']
		
		colorcode = min(127, max(0, colorcode))

		# TODO: Maybe the SysEx was indeed a better idea :)
		#       Did some tests:
		#         MacOS:   doesn't matter;
		#         Windoze: SysEx much better;
		#         Linux:   completely freaks out
		for x in range(9):
			for y in range(9):
				# TODO
				self.midi.RawWrite(144, (x + 1) + ((y + 1) * 10), colorcode)


	#-------------------------------------------------------------------------------------
	#-- Returns the raw value of the last button change (pressed/unpressed) as a list
	#-- [ <x>, <y>, <value> ], in which <x> and <y> are the buttons coordinates and
	#-- <value> is the intensity from 0..127.
	#-- >0 = button pressed; 0 = button released
	#-- Notice that this is not (directly) compatible with the original ButtonStateRaw()
	#-- method in the "Classic" Launchpad, which only returned [ <button>, <True/False> ].
	#-- Compatibility would require checking via "== True" and not "is True".
	#-------------------------------------------------------------------------------------
	def ButtonStateXY( self, mode = "classic", returnPressure = False ):
		if self.midi.ReadCheck():
			a = self.midi.ReadRaw()

			# 8/2020: Try to mitigate too many pressure events that a bit (yep, seems to work fine!)
			# 9/2020: XY now also with pressure event functionality
			if returnPressure == False:
				while a[0][0][0] == 208:
					a = self.midi.ReadRaw()
					if a == []:
						return []

			if a[0][0][0] == 144 or a[0][0][0] == 176:
			
				if mode.lower() != "pro":
					x = (a[0][0][1] - 1) % 10
				else:
					x = a[0][0][1] % 10
				if a[0][0][1] > 99:
					y = 9
				elif a[0][0][1] < 10:
					y = 10
				else:
					y = ( 99 - a[0][0][1] ) // 10
			
				return [ x, y, a[0][0][2] ]
			else:
				# TOCHK: this should be safe without checking "returnPressure"
				if a[0][0][0] == 208:
					return [ 255, 255, a[0][0][1] ]
				else:
					return []
		else:
			return []


	#-------------------------------------------------------------------------------------
	#-- (fake to) reset the Launchpad
	#-- Turns off all LEDs
	#-------------------------------------------------------------------------------------
	def Reset( self ):
		self.LedAllOn( 0 )


	#-------------------------------------------------------------------------------------
	#-- Go back to custom modes before closing connection
	#-- Otherwise Launchpad will stuck in programmer mode
	#-------------------------------------------------------------------------------------
	def Close( self ):
		# re-enter Live mode
		if self.midi.devIn != None and self.midi.devOut != None:
			self.LedSetMode( 0 )
		# TODO: redundant (but needs fix for Py2 embedded anyway)
		# self.midi.CloseInput()
		# self.midi.CloseOutput()
