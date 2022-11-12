#!/usr/bin/env python

# Tester for the serial buffet Pico
# Sends data to /dev/serial0 TxD (gpio pin 8), receives on RxD(gpio pin 10) and verifies that no data is missing
# RTS on gpio17 (pin 11) chokes the Rx to simulate a rate limited radio module
# Note: I could not get the HW RTS control on the RP400 to work, so a manual control is implementes on the RTS pin
#
import datetime
import time
import serial
import RPi.GPIO as gpio
import os
import sys
#import numpy as np

testList = [16, 128, 1024, 10*1024+10]
testList = [16, 16, 16, 16]
testList = [512]
CTSchannel = "16"
RTSchannel = "17"
RTS_ENABLE = gpio.LOW
RTS_DISABLE = gpio.HIGH
PKG_LEN = 8 # Size of test package without the two delimiters
rxCnt = 0

# Instantiate a serial port
# The same port is used for both Tx and Rx
ser = serial.Serial(
	port='/dev/serial0',
	baudrate = 38400,
	parity=serial.PARITY_NONE,
	stopbits=serial.STOPBITS_ONE,
	bytesize=serial.EIGHTBITS,
	timeout=1
)
# Transmitted test strings are saved for cmparison on Rx
testBuffer = []

# Transmit function
def transmitPackage(payload):
	#tstamp = str(datetime.datetime.now().microsecond).encode()
	# Add pre- and postamble
	txString = "<" + str(payload) + ">"
	# write to serial port
	ser.write(txString.encode())
	# Save in buffer for test on Rx
	testBuffer.append(txString)	
	while(ser.out_waiting > 0): # Wait for the UART to empty its internal buffer
		time.sleep(0.001)
# End of transmitPackage

def receiveAll():
	rxCnt = 0
	inputData = ""							# Empty string to collect Rx
	while (True):
		gpio.output(17, RTS_ENABLE)  	# pulse-enable RTS
		time.sleep(0.001)
		gpio.output(17, RTS_DISABLE)
		time.sleep(0.01)				# Wait until tx done
		if (ser.in_waiting == 0):		# Any chars received?
			break						# No, terminate Rx cycle
		#print(ser.in_waiting, end = '\r')
		while (ser.in_waiting > 0):		# Empty uart internal buffer
			inputData = inputData + (ser.read().decode())
			if (inputData[-1]) == '>':
				print("Rx # " + str(rxCnt) + ": " + f'{inputData[-PKG_LEN-2:]:<12}', end = "\r", flush=True)
				rxCnt += 1
	return inputData

# Compare an input string comprised of "< ... >" delimited packages
# To a buffer containing the reference packages
def compareRxTx(inputString, testBuffer):
	identity=False
	inputIdx = 0
	while inputIdx < len(inputString):			# Through input string
		inputPackage = inputString[inputIdx : inputString.find('>', inputIdx)+1] # Extract package 
		refPackage = testBuffer.pop(0) 	# Get reference package
		inputIdx += len(inputPackage) 	# advance buffer pointer
		identity = (inputPackage == refPackage) # Verify integrity
		#print ('\033[K', end = '')   # clear line
		print (f'{inputPackage:<12}' + " equals " + f'{refPackage:<12}' + " ? :" + f'{str(identity):<10}', end = "\r", flush=True)
		sys.stdout.flush()
		#time.sleep(0.1)
		if (not identity):
			break
	return (identity)

# Enable GPIO17 as an ordinary output (could not get the HW handshake to work in RP400)
gpio.setwarnings(False)
gpio.setmode(gpio.BCM)
gpio.setup(17, gpio.OUT)

# Flush the comm line for old buffer contents
print ("Flushing DUT")
inputLine = receiveAll()
inputLine = receiveAll()

# Test with varying fill levels of the buffer. 
# for a 10k char buffer plus UART internal buffers and 10 char packages, we expect failure somewhere over over 1k packages Txed without Rx 
# so the last test loads the buffer to failure, validating the test.
for bufferLoad in testList:
	print("\nTx started, " + str(bufferLoad) + " packages.")
	for txCount in range(bufferLoad):
		# Transmit
		txFormat = '%0' + str(PKG_LEN) + 'd'
		#txString = "%08d" %txCount  # Fixed length package, for easy debug
		txString = txFormat %txCount  # Fixed length package, for easy debug
		print("\rTx # " + txString, end = '\r')
		# Send package
		transmitPackage(txString)

	# read the buffered data back and test integrity
	print ("\nRx started, expecting "  + str(bufferLoad) + " packages.")
	# Empty the buffer
	inputLine =	receiveAll() 
	# if (len(inputLine) > 0):
		# print("Input (" + str(len(inputLine)) + " chars): " + inputLine, end = '\n')
	# Test for identity to txed data
	print ('\nReceived buffer, comparing to reference')
	if not compareRxTx(inputLine, testBuffer):  # Rx identical to Tx?
		print("\n*** Rx test error: Rx not equal Tx ***\n")		# No, exit with error message
		exit()		#
	else:
		print("\nTest with "   + str(bufferLoad) + " packages terminated OK." ) 
print ("\nTest terminated.")
