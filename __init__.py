from .comfygel import *

NODE_CLASS_MAPPINGS = {
    
    "Gelbooru (Random)" : GelbooruRandom,
    "Gelbooru (ID)" : GelbooruID,
    "UrlsToImage": UrlsToImage,
}


__all__ = ['NODE_CLASS_MAPPINGS']

print('loading...')