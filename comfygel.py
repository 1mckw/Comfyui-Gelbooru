import requests
import json
from PIL import Image, ImageOps


class GelbooruRandom:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "input_tags": ("STRING", {"default": "", "multiline": True}),
                "exclude_tag": ("STRING", {"default": "animated,", "multiline": True}),
                "note_area": ("STRING",{"default": "common tags:absurdres, highres,\nrating:rating:general,\nrating:sensitive,\nrating:questionable,\nrating:explicit, ", "multiline": True}),
                "score": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "user_id": ("STRING", {"default": "1414144"}),
                "api_key": ("STRING", {"default": "ed9a8f6ba574732b7401b78fa0d278133431911f8504740a526f36785db62e41"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "count": ("INT", {"default": 1, "min": 1, "max": 100}),
            },
            
        }
        
    RETURN_TYPES = ("STRING","STRING","STRING", "INT", "INT", "STRING",)
    RETURN_NAMES = ("imgtags","imgurl","imgid","width", "height", "source",)
    FUNCTION = "get_value"
    CATEGORY = "Gelbooru"

    def get_value(self, input_tags, exclude_tag, note_area, score, user_id, api_key, seed, count, ):
        inputtags = '+'.join(item.strip().replace(' ', '_').replace('\\', '') for item in (input_tags + ',').split(','))
        excludetags = '+'.join('-' + item.strip().replace(' ', '_') for item in exclude_tag.split(','))
        score, count = str(score), str(count)
        url = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&tags=sort%3arandom+"+excludetags+"+"+inputtags+"score%3a>"+score+"&api_key="+api_key+"&user_id="+user_id+"&limit="+count+"&json=1"
        url=url.replace("-+", "")
        posts = requests.get(url).json()['post']
        imgtags = '\n'.join(post.get("tags", "").replace(" ", ", ") for post in posts)
        imgurl = '\n'.join(post.get("file_url", "") for post in posts)
        imgid = '\n'.join(str(post.get("id", "")) for post in posts)
        width = '\n'.join(str(post.get("width", 0)) for post in posts)
        height = '\n'.join(str(post.get("height", 0)) for post in posts)
        source = '\n'.join(post.get("source", "") for post in posts)

        return (imgtags, imgurl, imgid, width, height, source,)


class GelbooruID:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "post_id": ("STRING", {"default": ""}),
            },
        }
        
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("tags", "imgurl",)
    FUNCTION = "get_value"
    CATEGORY = "Gelbooru"
  
    def get_value(self, post_id):
        url = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&id="+post_id+"&json=1"
        posts = requests.get(url).json()["post"]
        imgtags = []
        imgurl = []
        for post in posts:
            tags = post["tags"].replace(" ", ", ")
            imgurl = post["file_url"]
            imgtags.append(tags)
        return (imgtags, imgurl,)

NODE_DISPLAY_NAME_MAPPINGS = {
    "GelbooruRandom": "Gelbooru (Random)",
    "GelbooruID": "Gelbooru (ID)",
}
