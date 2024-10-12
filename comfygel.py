import requests
import json
from PIL import Image, ImageOps
import re

class GelbooruRandom:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "site":(["Gelbooru", "Rule34"],{}),
                "OR_tags": ("STRING", {"default": "", "multiline": True}),
                "AND_tags": ("STRING", {"default": "", "multiline": True}),
                "exclude_tag": ("STRING", {"default": "animated,", "multiline": True}),
                "note_area": ("STRING",{"default": "", "multiline": True}),
                "Safe": ("BOOLEAN", {"default": True}),
                "Questionable": ("BOOLEAN", {"default": True}),
                "Explicit": ("BOOLEAN", {"default": True}),
                "score": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "user_id": ("STRING", {"default": ""}),
                "api_key": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "count": ("INT", {"default": 1, "min": 1, "max": 100}),

            },
        }
        
    RETURN_TYPES = ("STRING","STRING","STRING", "INT", "INT", "STRING","STRING",)
    RETURN_NAMES = ("imgtags","imgurl","imgid","width", "height", "source", "url",)
    FUNCTION = "get_value"
    CATEGORY = "Gelbooru"

    def get_value(self, site, OR_tags, AND_tags, exclude_tag, note_area, score, user_id, api_key, seed, count, Safe, Questionable, Explicit):
        #AND_tags
        AND_tags = AND_tags.rstrip(',').rstrip(' ')
        AND_tags = AND_tags.split(',')
        AND_tags = [item.strip().replace(' ', '_').replace('\\', '') for item in AND_tags]
        AND_tags = [item for item in AND_tags if item]
        if len(AND_tags) > 1:
            AND_tags = '+'.join(AND_tags)
        else:
            AND_tags = AND_tags[0] if AND_tags else ''
        #OR_tags
        OR_tags = OR_tags.rstrip(',').rstrip(' ')
        OR_tags = OR_tags.split(',')
        OR_tags = [item.strip().replace(' ', '_').replace('\\', '') for item in OR_tags]
        OR_tags = [item for item in OR_tags if item]
        if len(OR_tags) > 1:
             if site == "Rule34":
                OR_tags = '( ' + ' ~ '.join(OR_tags) + ' )'
             else:
                OR_tags = '{' + ' ~ '.join(OR_tags) + '}'
        else:
            OR_tags = OR_tags[0] if OR_tags else ''

        exclude_tag = '+'.join('-' + item.strip().replace(' ', '_') for item in exclude_tag.split(','))
        
        score, count = str(score), str(count)

        rate_exclusion = ""
        
        if not Safe: 
            if site == "Rule34":
                rate_exclusion += "+-rating%3asafe"
            elif site == "Gelbooru":
                rate_exclusion += "+-rating%3ageneral"

        if not Questionable: 
            if site == "Rule34":
                rate_exclusion += "+-rating%3aquestionable" 
            elif site == "Gelbooru":
                rate_exclusion += "+-rating%3aquestionable+-rating%3aSensitive"

        if not Explicit: 
            if site == "Rule34":
                rate_exclusion += "+-rating%3aexplicit" 
            elif site == "Gelbooru":
                rate_exclusion += "+-rating%3aexplicit" 

        
        if site == "Rule34":
            base_url = "https://api.rule34.xxx/index.php"
        else:
            base_url = "https://gelbooru.com/index.php"
      
        query_params = (
            f"page=dapi&s=post&q=index&tags=sort%3arandom+"
            f"{exclude_tag}+{OR_tags}+{AND_tags}+{rate_exclusion}"
            f"+score%3a>{score}&api_key={api_key}&user_id={user_id}&limit={count}&json=1"
        )
        url = f"{base_url}?{query_params}".replace("-+", "")
        url = re.sub(r"\++", "+", url)
        
        response = requests.get(url, verify=True)

        if site == "Rule34":
            posts = response.json()
        else:
            posts = response.json().get('post', [])

        imgtags = '\n'.join(post.get("tags", "").replace(" ", ", ") for post in posts)
        imgurl = '\n'.join(post.get("file_url", "") for post in posts)
        imgid = '\n'.join(str(post.get("id", "")) for post in posts)
        width = '\n'.join(str(post.get("width", 0)) for post in posts)
        height = '\n'.join(str(post.get("height", 0)) for post in posts)
        source = '\n'.join(post.get("source", "") for post in posts)
        
        return (imgtags, imgurl, imgid, width, height, source, url,)

class GelbooruID:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "post_id": ("STRING", {"default": ""}),
            },
        }
        
    RETURN_TYPES = ("STRING","STRING","STRING", "INT", "INT", "STRING",)
    RETURN_NAMES = ("imgtags","imgurl","imgid","width", "height", "source", )
    FUNCTION = "get_value"
    CATEGORY = "Gelbooru"
  
    def get_value(self, post_id):
        url = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&id="+post_id+"&json=1"
        posts = requests.get(url).json()["post"]

        imgtags = '\n'.join(post.get("tags", "").replace(" ", ", ") for post in posts)
        imgurl = '\n'.join(post.get("file_url", "") for post in posts)
        imgid = '\n'.join(str(post.get("id", "")) for post in posts)
        width = '\n'.join(str(post.get("width", 0)) for post in posts)
        height = '\n'.join(str(post.get("height", 0)) for post in posts)
        source = '\n'.join(post.get("source", "") for post in posts)
        return (imgtags, imgurl, imgid, width, height, source, )


NODE_DISPLAY_NAME_MAPPINGS = {
    "GelbooruRandom": "Gelbooru (Random)",
    "GelbooruID": "Gelbooru (ID)",
    "Pose filter" : "Posefilter",
}
