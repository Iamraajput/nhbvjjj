import pyrogram.utils as utils
import inspect

source = inspect.getsource(utils.get_peer_type)
print(source)
