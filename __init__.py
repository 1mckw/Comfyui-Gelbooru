from .comfygel import *

NODE_CLASS_MAPPINGS = {
    
    "Gelbooru (Random)" : GelbooruRandom,
    "Gelbooru (ID)" : GelbooruID,
}

__all__ = ['NODE_CLASS_MAPPINGS']

print('loading...')