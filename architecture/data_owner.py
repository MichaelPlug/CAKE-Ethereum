import socket
import ssl
from hashlib import sha512
import json
from decouple import config
import sqlite3
import argparse

process_instance_id = config('PROCESS_INSTANCE_ID')

HEADER = 64
PORT = int(config('SDM_PORT'))
FORMAT = 'utf-8'
server_sni_hostname = config('SERVER_SNI_HOSTNAME')
DISCONNECT_MESSAGE = "!DISCONNECT"
SERVER = config('SERVER')
ADDR = (SERVER, PORT)
server_cert = 'Keys/server.crt'
client_cert = 'Keys/client.crt'
client_key = 'Keys/client.key'

# Connection to SQLite3 data_owner database
connection = sqlite3.connect('files/data_owner/data_owner.db')
x = connection.cursor()

"""
creation and connection of the secure channel using SSL protocol
"""

context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=server_cert)
context.load_cert_chain(certfile=client_cert, keyfile=client_key)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
conn = context.wrap_socket(s, server_side=False, server_hostname=server_sni_hostname)
conn.connect(ADDR)

manufacturer_address = config('ADDRESS_MANUFACTURER')


def sign_number():
    x.execute("SELECT * FROM handshake_number WHERE process_instance=?", (process_instance_id,))
    result = x.fetchall()
    number_to_sign = result[0][2]

    x.execute("SELECT * FROM rsa_private_key WHERE reader_address=?", (sender,))
    result = x.fetchall()
    private_key = result[0]
    private_key_n = int(private_key[1])
    private_key_d = int(private_key[2])

    msg = bytes(str(number_to_sign), 'utf-8')
    hash = int.from_bytes(sha512(msg).digest(), byteorder='big')
    signature = pow(hash, private_key_d, private_key_n)
    # print("Signature:", hex(signature))
    return signature


"""
function to handle the sending and receiving messages.
"""


def send(msg):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    conn.send(send_length)
    conn.send(message)
    receive = conn.recv(6000).decode(FORMAT)
    if receive.startswith('Number to be signed: '):
        len_initial_message = len('Number to be signed: ')
        x.execute("INSERT OR IGNORE INTO handshake_number VALUES (?,?,?)",
                    (process_instance_id, sender, receive[len_initial_message:]))
        connection.commit()
    if receive.startswith('Here is the message_id:'):
        receive = receive.split('\n ')[0]
        x.execute("INSERT OR IGNORE INTO messages VALUES (?,?,?)", (process_instance_id, sender, receive[16:]))
        connection.commit()


# f = open('files/data.json')
g = open('files/data.json')

message_to_send = g.read()

###########
###########
###########
###LINES###
###########
###########
###########

# policy_string = '1604423002081035210 and (MANUFACTURER or (SUPPLIER and ELECTRONICS))'

entries = [['ID', 'SortAs', 'GlossTerm'], ['Acronym', 'Abbrev'], ['Specs', 'Dates']] 
entries_string = '###'.join(str(x) for x in entries)

policy = [str(process_instance_id) + ' and (MANUFACTURER or SUPPLIER)',
          str(process_instance_id) + ' and (MANUFACTURER or (SUPPLIER and ELECTRONICS))',
          str(process_instance_id) + ' and (MANUFACTURER or (SUPPLIER and MECHANICS))']
policy_string = '###'.join(policy)

# data = json.load(f)
# entries = list(data.keys())
# entries_string = '###'.join(entries)
# print(entries_string)
# exit()

# entries_string = ''

sender = manufacturer_address

parser = argparse.ArgumentParser()
parser.add_argument('-hs' ,'--hanshake', action='store_true')
parser.add_argument('-c','--cipher', action='store_true')

args = parser.parse_args()
if args.hanshake:
    send("Start handshake§" + sender)

if args.cipher:
    signature_sending = sign_number()
    send("Cipher this message§" + message_to_send + '§' + entries_string + '§' + policy_string + '§' + sender + '§' + str(signature_sending))

send(DISCONNECT_MESSAGE)
