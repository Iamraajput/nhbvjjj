import pyrogram.utils as utils
import inspect

source = inspect.getsource(utils.get_peer_type)
with open("source_get_peer_type.txt", "w", encoding="utf-8") as f:
    f.write(source)
print("Source written to source_get_peer_type.txt")

# Also print some relevant constants
try:
    print(f"MIN_CHAT_ID: {getattr(utils, 'MIN_CHAT_ID', 'N/A')}")
    print(f"MIN_CHANNEL_ID: {getattr(utils, 'MIN_CHANNEL_ID', 'N/A')}")
    print(f"MAX_CHANNEL_ID: {getattr(utils, 'MAX_CHANNEL_ID', 'N/A')}")
    print(f"MAX_USER_ID_OLD: {getattr(utils, 'MAX_USER_ID_OLD', 'N/A')}")
except:
    pass
