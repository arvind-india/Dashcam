
import serial
import io
import time
import re
import sys
import mysql.connector
import pynmea2
import threading
import string
import random
import os

mydb = mysql.connector.connect(
  host="localhost",
  user="root",
  passwd="root",
  database="Dashcam"
)

TripID = ""
RPM = 0
KMH = 0
CTemp = 0
ATemp = 0
TPos = 0

Lon = 0.0
Lat = 0.0

done = 1
gpsdone = 1

TripID = str(sys.argv[1])
print("TripID: "+TripID)

s = 0

#Add Trip to database
mydb.cursor().execute("INSERT INTO Trip (TripID, Date) VALUES (%s,CURRENT_TIMESTAMP)", (TripID,))
mydb.commit()

def _readline(s):
    eol = b'\r'
    leneol = len(eol)
    line = bytearray()
    while True:
        c = s.read(1)
        if c:
            line += c
            if line[-leneol:] == eol:
                break
        else:
            break
    return bytes(line)


def updateGPS(GPSser):
	global Lat, Lon, gpsdone
	try:
		raw = GPSser.read(1200)
		result = re.search("GPGGA(.*)\r",raw.decode() )
		msg = pynmea2.parse("$GPGGA"+result.group(1) )
		if msg.latitude != 0.0 and msg.longitude != 0.0:
			Lon = msg.latitude
			Lat = msg.longitude
	except Exception as ex:
			print("Could not update GPS Loc")
	gpsdone = 1
	return

def updateOBD():
	global RPM, KMH, CTemp, ATemp, done, s, TPos
	try:
		r = sendCommand('0D')
		if "error" not in r:
			KMH = int(r[0],16)

		r = sendCommand('0C')
		if "error" not in r:
			RPM = ( 256 * int(r[0],16) + int(r[1],16) ) / 4

		r = sendCommand('05')
		if "error" not in r:
			CTemp = int(r[0],16) - 40

		r = sendCommand('0F')
		if "error" not in r:
			ATemp = int(r[0],16) - 40

		r = sendCommand('11')
		if "error" not in r:
			TPos =  (100 / 255) * int(r[0],16)
	except Exception as ex:
		print("Could not connect to OBDII retrying")
		print(ex)
	done = 1
	return
	

errorCount = 0
def sendCommand( str ):
	global s, errorCount
	pid = str
	str = '01 ' + str + '1'
	s.write(str.encode()+'\r\n'.encode())
	s.flushInput()
	res = _readline(s)
	result = re.search('41 ' + pid+' (.*) ', res.decode())
	s.reset_input_buffer()
	try:
		out = result.group(1).split(' ')
		return out
	except AttributeError:
		#print("")
		return ["00","00","00","error"]


while 1:
	try:
		s = serial.Serial('/dev/rfcomm0', 115200, timeout=1)
		GPSser = serial.Serial('/dev/ttyAMA0', 9600,timeout=0.1)
		s.write('ATZ\r\n'.encode())
		time.sleep(2)
		s.write('ATE0\r\n'.encode())
		s.flushInput()
		while 1:
			
			if done == 1:			
				o = threading.Thread(target=updateOBD, args=())
				o.start()
				done = 0
			if gpsdone == 1:
				t = threading.Thread(target=updateGPS, args=(GPSser,))
				t.start()
				gpsdone = 0
						
			time.sleep(1)
			#print ("RPM="+str(RPM)+" KM/H="+str(KMH)+" Coolant temp="+str(CTemp)+" Air temp="+str(ATemp)+" Throttle="+str(TPos)+" GPS="+str(Lon))
			#Add TripLog to database
			ID = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
			mydb.cursor().execute("INSERT INTO TripData (ID, TripID, RPM, Speed, Throttle, CTemp, ATemp, Lon, Lat) VALUES (%s, %s,%s,%s,%s,%s,%s,%s,%s)", (ID, TripID, int(RPM), int(KMH), int(TPos), int(CTemp), int(ATemp), Lon, Lat))
			mydb.commit()
		
	except Exception as ex:
		print("something wong")
		print(ex)
