from pywebostv.discovery import discover
from pywebostv.connection import WebOSClient
from pywebostv.controls import InputControl, MediaControl, SystemControl

import os
import json
import time

FILE_STORE_NAME = "connection_settings.store"

# The first time the software is run, we don't have connection infos, so we need to retrieve them.
# Just check if the file connection_store is already present in the root folder of the python script;
# If positive, load connection infos from there, otherwise declare store as an emtpy dictionary,
# it will be populated at first successful connection attempt and later will be saved to disk.

if os.path.exists(FILE_STORE_NAME) and (os.path.getsize(FILE_STORE_NAME)!=0):
    with open(FILE_STORE_NAME, "r") as file:
        store = json.load(file)
else:
    store = {}

# Scans the current network to discover TV. Avoid [0] in real code. If you already know the IP,
# you could skip the slow scan and # instead simply say:
#    client = WebOSClient("<IP Address of TV>")
# or for newer models:
#    client = WebOSClient("<IP Address of TV>", secure=True)
client = WebOSClient.discover(secure=True)[0] # Use discover(secure=True) for newer models.
client.connect()
for status in client.register(store):
    if status == WebOSClient.PROMPTED:
        print("Please accept the connect on the TV!")
    elif status == WebOSClient.REGISTERED:
        print("Registration successful!")

# Keep the 'store' object because it contains now the access token
# and use it next time you want to register on the TV.
print(store)   # {'client_key': 'ACCESS_TOKEN_FROM_TV'}

# Save the configuration of the connection
with open(FILE_STORE_NAME, "w") as file:
    json.dump(store, file)


system = SystemControl(client)

media = MediaControl(client)
media.set_volume(5)    # The argument is an integer from 1 to 100. Doesn't return anything.
time.sleep(10)
media.mute(status)         # status=True mutes the TV. status=Fale unmutes it.
time.sleep(18)


""" media.play()
media.pause()
media.stop()
media.rewind()
media.fast_forward()
 """
