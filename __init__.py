from .comfygel import *

from .tag_rules import TagRules

NODE_CLASS_MAPPINGS = {
    "Gelbooru (Random)": GelbooruRandom,
    "Gelbooru (ID)": GelbooruID,
    "UrlsToImage": UrlsToImage,
    "TagRules": TagRules,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Gelbooru (Random)": "Gelbooru (Random)",
    "Gelbooru (ID)": "Gelbooru (ID)",
    "UrlsToImage": "UrlsToImage",
    "TagRules": "Gelbooru (Tag Rules - Replace & Remove)",
}

# Served by ComfyUI at /extensions/Comfyui-Gelbooru/ and auto-loaded by the frontend.
WEB_DIRECTORY = "./web"


__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print('loading...')
