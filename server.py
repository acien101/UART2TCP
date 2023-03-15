#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 15 10:06:52 2023

@author: facien
"""

# Start a TCP Socket

import socket
import threading
import queue
import select
import time
import serial



DEBUG = False # Prints messages

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)
BAUDRATE = 115200 # Arbitrary number
SERIALPORT = '/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0'

q_in_ser = queue.Queue()                     # Input Queue from the Serial
q_out_ser = queue.Queue()                    # Output Queue to the Serial

server_active = False
active_users = []
check_conn_timemout = 1

def on_new_client(conn,addr):
  print(f"Connected by {addr}")
  active_users.append(conn)
  while server_active:
    
    ready = select.select([conn], [], [], check_conn_timemout)
    if ready[0]:
      data = conn.recv(1024)      # Receive data
      q_out_ser.put(data)         # Put the received data on the queue
      if not data:  # Close the Thread
        if DEBUG:
          print("Clossing {}".format(addr))
        break
  if DEBUG:
    print("Closing {}".format(addr))
  conn.close()
  active_users.remove(conn)


def sendTCP(conn, data):
  if not conn:
    print("There is no available connection")
    return
  
  if DEBUG:
      print("Sending data to TCP")
  conn.sendall(data)

# If there is any data on the q_in_ser, post it on the TCP
def TCP_writer():
  while server_active:
    item = q_in_ser.get() # Get items from the queue if there are any
    if DEBUG:
      print("TCP_WRITER: Received item: {}".format(item))
    
    # Send data to all TCP connections
    for conn in active_users:
      sendTCP(conn, item)
    
    q_in_ser.task_done()

# Start Serial port read
# Read from Serial port and send it to the FIFO


ser = serial.Serial(SERIALPORT, 
                    baudrate=BAUDRATE, bytesize=8, parity=serial.PARITY_NONE)  # open serial port

# Read if the is data from the UART, if the is any add to the q_in_ser
def UART_listener():
  print("UART_LISTENER: Starting listening")
  while server_active:
    #read data from serial port
    ready = select.select([ser], [], [], check_conn_timemout)
    if ready[0]:
      i_data = ser.readline()
  
      #if there is smth do smth
      if len(i_data) >= 1:
        if DEBUG:
          print("UART_LISTENER: Received item: {}".format(i_data))
        
        if len(active_users) >= 1: # Send to queue only if there are users listening
          # Send the received data to the FIFO
          q_in_ser.put(i_data)
  print("Stop listening UART port")      

# If there is any data on the queue q_out_ser wri'te it to the serial port
def UART_writer():
  while server_active:
    item = q_out_ser.get() # Get items from the queue if there are any
    if DEBUG:
      print("UART_WRITER: Writting to UART: {}".format(item))
    
    # Send to the serial port
    ser.write(item)
    
    q_out_ser.task_done()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()

server_active = True
threading.Thread(target=TCP_writer, daemon=True).start()
threading.Thread(target=UART_listener, daemon=True).start()
threading.Thread(target=UART_writer, daemon=True).start()

try:
  while True:
    conn, addr = s.accept()     # Listening for connections
    threading.Thread(target=on_new_client, args=(conn, addr), daemon=True).start()
    pass
except KeyboardInterrupt:
  print('Closing program.\nClosing opened connections.\nClosing socket\nClosing serial port')
  server_active = False
  time.sleep(check_conn_timemout)   # Timeout used when listening on the on_new_client
  s.close()   #Close socket
  ser.close() # Close serial port
