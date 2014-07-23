#!/usr/bin/python

########################################################################
# Description: temp.py												 #
# This code reads an ADC input on the BeagleBone and converts the	  #
# resulting value into a temperature according to the thermistor	   #
# type, accounting for the analog input circuty as implemented on	  #
# the BeBoPr cape													  #
#																	  #
# Author(s): Charles Steinkuehler									  #
# License: GNU GPL Version 2.0 or (at your option) any later version.  #
#																	  #
# Major Changes:													   #
# 2013-June   Charles Steinkuehler									 #
#			 Initial version										  #
########################################################################
# Copyright (C) 2013  Charles Steinkuehler							 #
#					 <charles AT steinkuehler DOT net>				#
#																	  #
# This program is free software; you can redistribute it and/or		#
# modify it under the terms of the GNU General Public License		  #
# as published by the Free Software Foundation; either version 2	   #
# of the License, or (at your option) any later version.			   #
#																	  #
# This program is distributed in the hope that it will be useful,	  #
# but WITHOUT ANY WARRANTY; without even the implied warranty of	   #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the		#
# GNU General Public License for more details.						 #
#																	  #
# You should have received a copy of the GNU General Public License	#
# along with this program; if not, write to the Free Software		  #
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA		#
# 02110-1301, USA.													 #
#																	  #
# THE AUTHORS OF THIS PROGRAM ACCEPT ABSOLUTELY NO LIABILITY FOR	   #
# ANY HARM OR LOSS RESULTING FROM ITS USE.  IT IS _EXTREMELY_ UNWISE   #
# TO RELY ON SOFTWARE ALONE FOR SAFETY.  Any machinery capable of	  #
# harming persons must have provisions for completely removing power   #
# from all motors, etc, before persons enter any danger area.  All	 #
# machinery must be designed to comply with local and national safety  #
# codes, and the authors of this software can not, and do not, take	#
# any responsibility for such compliance.							  #
########################################################################

import argparse
import glob
import sys
import time

import hal


# The BeBoPr board thermistor input has one side grounded and the other side
# pulled high through a 2.05K resistor to 3.6V.  Following this is a 470R
# resistor, some protection diodes, and a voltage divider cosisting of two
# 10.0K resistors.  The ADC voltage read is the voltage across the lower 10K
# resistor in the 470R + 10K + 10K series chain
def adc2r(V_adc):
	V_T  = 0.0  # Voltage across the thermistor (and the 470R + 10K + 10K resistor chain)
	I_PU = 0.0  # Current flowing through the 2.05K pull-up resistor
	R_TD = 0.0  # Resistance of thermistor and the 470R + 10K + 10K divider chain in parallel
	R_T  = 0.0  # Resistance of the thermistor

	V_T = V_adc * 2.0470

	# No dividing by zero or negative voltages despite what the ADC says!
	# Clip to a small positive value
	I_PU = max((3.6 - V_T ) / 2050, 0.000001)   

	R_TD = V_T / I_PU

	# Acutal resistance can't be negative, but we can get a negative value
	# from the equation below for some real ADC values, so clip to avoid
	# reporting crazy temperature values or dividing by zero
	if R_TD >= 20470 :
		R_TD = 20470 - 0.1

	# 1 / Rtotal = 1 / ( 1 / R1 + 1 / R2 )
	# R2  = ( R1 * Rtotal ) / ( R1 - Rtotal )
	R_T  = ( 20470 * R_TD ) / ( 20470 - R_TD )

	# print "V_adc: %f V_T: %f  R_TD: %f  R_T: %f" % (V_adc, V_T, R_TD, R_T)
	

	return R_T

# Convert resistance value into temperature, using thermistor table
def r2t(n, R_T):
	temp_slope = 0.0
	temp	   = 0.0

	i = max(bisect.bisect_right(R_Key[n], R_T) - 1, 0)
	
	temp_slope = (thermistor[n][0][i] - thermistor[n][0][i+1]) / (thermistor[n][1][i] - thermistor[n][1][i+1])
	temp = thermistor[n][0][i] + ((R_T - thermistor[n][1][i]) * temp_slope)
	#print "Temp:", temp, "i.R_T:", i, R_T, "slope:", temp_slope, 
	#print "Deg.left:", Thermistor["epcos_B57560G1104"][i], "Deg.right:", Thermistor["epcos_B57560G1104"][i+1]
	return temp

parser = argparse.ArgumentParser(description='HAL component to read ADC values and convert to temperature')
parser.add_argument('-n','--name', help='HAL component name', required=True)
parser.add_argument('-a','--adc',  help='ADC input to read', required=True)
args = parser.parse_args()

adc_input = int(args.adc)

syspath = '/sys/devices/ocp.*/44e0d000.tscadc/tiadc/iio:device0/'

# test open input?
FileName = glob.glob (syspath + 'in_voltage' + args.adc + '_raw')
FileName = FileName[0]
try:
	if len(FileName) > 0:
		f = open(FileName, 'r')
		f.close()
		time.sleep(0.001)
	else:
		raise UserWarning('Bad Filename')
except (UserWarning, IOError) :
	print("Cannot read ADC input: %s" % Filename)
	sys.exit(1)


h = hal.component(args.name)
h.newpin("resistance", hal.HAL_FLOAT, hal.HAL_OUT)
h.newpin("trigger", hal.HAL_BIT, hal.HAL_OUT)
h.newpin("reset", hal.HAL_BIT, hal.HAL_IN)
h.ready()

Err = 0.0
ADC_V = 0.0
filteredValue = 0.0
filterMix = 0.01
filterMixI = 1.0 - filterMix

while 1:
	try:
		f = open(FileName, 'r')
		ADC_IN = int(f.readline())
		#ADC_V = float(ADC_IN) * 1.8 / 4096.0
		h.resistance = ADC_IN #adc2r(ADC_V)
		if filteredValue == 0.0 or h.reset:
			filteredValue = h.resistance
		h.trigger = h.resistance / max(filteredValue, 0.01) < 0.99
		#if not h.trigger:
		filteredValue = h.resistance * filterMix + filteredValue * filterMixI
		#print ADC_IN, h.resistance, filteredValue
		f.close()
		time.sleep(0.01)

	except IOError:
		continue

	except KeyboardInterrupt:
		raise SystemExit

