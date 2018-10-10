#! /usr/bin/env python2

import os
import socket
import sys
import time
from select import select

from ontask_messages import *

#Args: redstring_mythtv.py server port mythtv_frontend_ip

#Handle parameters
if len(sys.argv)!=4:
    print "Error: invalid parameters"
    exit(1)

server = sys.argv[1]
port = int(sys.argv[2])
mythtv_ip = sys.argv[3]

#Create server socket
server_conn_ = socket.socket()
server_conn_.connect((server,port))
server_conn = server_conn_.makefile()

#Create MythTV frontend control socket socket
mythtv_conn_ = socket.socket()
mythtv_conn_.connect((mythtv_ip,6546))
mythtv_conn = mythtv_conn_.makefile()

#Eat stupid "MythFrontend Network Control blah blah blah"
mythtv_conn.readline()
mythtv_conn.readline()
mythtv_conn.readline()
mythtv_conn.read(2)

#Name and group
print "Red String Connected; enter your name and group"
nick = raw_input("Name: ")
group = raw_input("Group: ")

#Send HELLO message to server
server_conn.write(OnTask_Message("HELLO",nick+"\n"+group).get_message_string())
server_conn.flush()

#Send command over MythTV FCS and eat response data
def send_mythtv_cmd(mythtv_cmd):
    mythtv_conn.write(mythtv_cmd+"\n")
    mythtv_conn.flush()
    response = mythtv_conn.readline()
    mythtv_conn.read(2)
    return response

def get_seekstr(body):
    seekpos = int(eval(body))
    hours = seekpos/3600
    minutes = (seekpos%3600)/60
    seconds = seekpos%60
    seekstr = repr(hours).zfill(2)+":"+repr(minutes).zfill(2)+":"+repr(seconds).zfill(2)
    return seekstr

def get_seekpos(seekstr):
    pieces = seekstr.split(":")
    to_return = 0
    i=0
    while i < len(pieces):
        to_return += int(pieces[i])*pow(60,len(pieces)-i-1)
        i=i+1
    return int(to_return)

#select()-based loop
should_be_paused = False
playback_pos = 0
while True:
    retvals = select((server_conn,sys.stdin),(),(),2)

    #Query server for current playback position
    try:
        newpos = get_seekpos(send_mythtv_cmd("query location").split(" ")[2])
    except ValueError:
        continue
    if should_be_paused:
        if newpos!=playback_pos:
            server_conn.write(OnTask_Message("PLAY","").get_message_string())
            server_conn.flush()
            should_be_paused = False
    else:
        if newpos - playback_pos > 5 or newpos - playback_pos < 0:
            server_conn.write(OnTask_Message("SEEK",repr(newpos)).get_message_string())
            server_conn.flush()
        elif newpos - playback_pos == 0:
            should_be_paused = True
            server_conn.write(OnTask_Message("PAUSE",repr(newpos)).get_message_string())
            server_conn.flush()
    playback_pos = newpos

    #Handle server notifications
    if server_conn  in retvals[0]:
        received_ontask = OnTask_Message.message_from_socket(server_conn)
        if received_ontask.cmd_id=="PAUSE":
            should_be_paused = True
            send_mythtv_cmd("play speed pause")
            send_mythtv_cmd("play seek "+get_seekstr(received_ontask.body))
            playback_pos = int(eval(received_ontask.body))
        elif received_ontask.cmd_id=="SEEK":
            send_mythtv_cmd("play seek "+get_seekstr(received_ontask.body))
            playback_pos = int(eval(received_ontask.body))
        elif received_ontask.cmd_id=="PLAY":
            should_be_paused = False
            send_mythtv_cmd("play speed normal")
        elif received_ontask.cmd_id=="CHAT":
            send_mythtv_cmd("notification "+received_ontask.body)
        elif received_ontask.cmd_id=="ROSTER":
            send_mythtv_cmd("notification ROSTER: "+", ".join(received_ontask.body.splitlines()))
        else: #invalid message; quit
            send_mythtv_cmd("notification Red String error; quitting")
            exit(1)

    #Handle chats
    if sys.stdin in retvals[0]:
        server_conn.write(OnTask_Message("CHAT",raw_input()).get_message_string())
        server_conn.flush()
