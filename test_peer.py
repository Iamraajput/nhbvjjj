import pyrogram
from pyrogram import utils
import os

peer_id = -1003889334129
try:
    p_type = utils.get_peer_type(peer_id)
    print(f"Peer ID: {peer_id}")
    print(f"Peer Type: {p_type}")
except Exception as e:
    print(f"Error for {peer_id}: {type(e).__name__}: {e}")

# Test with string
peer_id_str = "-1003889334129"
try:
    # get_peer_type usually expects int, but let's see
    p_type = utils.get_peer_type(int(peer_id_str))
    print(f"Peer ID Str: {peer_id_str}")
    print(f"Peer Type: {p_type}")
except Exception as e:
    print(f"Error for {peer_id_str}: {type(e).__name__}: {e}")

print(f"Pyrogram Version: {pyrogram.__version__}")
