#! /usr/bin/env python2

import os
import socket
import sys
import time
from select import select

from ontask_messages import *

#Args: redstring_client.py server port movie ["mpv --flag1 --flag2"]

#Handle parameters
if len(sys.argv)==4:
    system_cmd = "mpv --input-ipc-server=redstring.sock "+sys.argv[3]+" > /dev/null 2> /dev/null &"
elif len(sys.argv)==5:
    system_cmd = sys.argv[4]+" --input-ipc-server=redstring.sock "+sys.argv[3]+" > /dev/null 2> /dev/null &"
else:
    print "Error: invalid parameters"
    exit(1)
server = sys.argv[1]
port = int(sys.argv[2])

#Create server socket
server_conn_ = socket.socket()
server_conn_.connect((server,port))
server_conn = server_conn_.makefile()

#Name and group
print "Red String Connected; enter your name and group"
nick = raw_input("Name: ")
group = raw_input("Group: ")

#Start mpv
os.system(system_cmd)
time.sleep(1)

#Set up JSON IPC socket connection
ipc_conn_ = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
ipc_conn_.connect("redstring.sock")
ipc_conn = ipc_conn_.makefile()

#Send HELLO message to server
server_conn.write(OnTask_Message("HELLO",nick+"\n"+group).get_message_string())
server_conn.flush()

#Send command over JSON IPC and eat response date
null = None
def send_json_ipc(json_cmd):
    ipc_conn.write(json_cmd+"\n")
    ipc_conn.flush()
    received_json = eval(ipc_conn.readline())
    while "error" not in received_json:
        received_json = eval(ipc_conn.readline())
    return received_json["data"] if "data" in received_json else None

#select()-based loop
should_be_paused = False
while True:
    retvals = select((ipc_conn,server_conn,sys.stdin),(),())

    #Handle JSON IPC
    if ipc_conn in retvals[0]:
        received_json = eval(ipc_conn.readline())
        if "event" in received_json:
            #Handle telling server we paused
            if received_json["event"]=="pause" and not should_be_paused:
                should_be_paused = True
                server_conn.write(OnTask_Message("PAUSE",repr(send_json_ipc('{"command":["get_property","playback-time"]}'))).get_message_string())
                server_conn.flush()
            #Handle telling server we unpaused
            elif received_json["event"]=="unpause" and should_be_paused:
                should_be_paused = False
                server_conn.write(OnTask_Message("PLAY","").get_message_string())
                server_conn.flush()
            elif received_json["event"]=="seek":
                server_conn.write(OnTask_Message("SEEK",repr(send_json_ipc('{"command":["get_property","playback-time"]}'))).get_message_string())
                server_conn.flush()

    #Handle server notifications
    if server_conn  in retvals[0]:
        received_ontask = OnTask_Message.message_from_socket(server_conn)
        if received_ontask.cmd_id=="PAUSE":
            should_be_paused = True
            send_json_ipc('{"command":["seek",'+received_ontask.body+',"absolute"]}')
            send_json_ipc('{"command":["set_property","pause",true]}')
        elif received_ontask.cmd_id=="SEEK":
            send_json_ipc('{"command":["seek",'+received_ontask.body+',"absolute"]}')
            received_json = eval(ipc_conn.readline())
            while "event" not in received_json or received_json["event"]!="seek":
                received_json = eval(ipc_conn.readline())                
        elif received_ontask.cmd_id=="PLAY":
            should_be_paused = False
            send_json_ipc('{"command":["set_property","pause",false]}')
        elif received_ontask.cmd_id=="CHAT":
            send_json_ipc('{"command":["show-text","'+received_ontask.body.replace("\\","\\\\").replace('"','\\"')+'",6000]}')
        elif received_ontask.cmd_id=="ROSTER":
            send_json_ipc('{"command":["show-text","ROSTER: '+", ".join(received_ontask.body.splitlines())+'",3000]}')
        else: #invalid message; quit
            print "ERROR: invalid command "+recevied_ontask.cmd_id+" received from server."
            send_json_ipc('{"command":["quit"]}')
            exit(1)

    #Handle chats
    if sys.stdin in retvals[0]:
        server_conn.write(OnTask_Message("CHAT",raw_input()).get_message_string())
        server_conn.flush()
