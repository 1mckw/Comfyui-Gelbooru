import requests
import json


class GelbooruRandom:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "OR_tags": ("STRING", {"default": "", "multiline": True}),
                "AND_tags": ("STRING", {"default": "", "multiline": True}),
                "exclude_tag": ("STRING", {"default": "animated,", "multiline": True}),
                "note_area": ("STRING",{"default": "common tags:\nrating:rating:general,\nrating:sensitive,\nrating:questionable,\nrating:explicit, ", "multiline": True}),
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

    def get_value(self,OR_tags, AND_tags, exclude_tag, note_area, score, user_id, api_key, seed, count, ):
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
            OR_tags = ' ~ '.join(OR_tags)
            OR_tags = '{' + OR_tags + '}'
        else:
            OR_tags = OR_tags[0] if OR_tags else ''

        exclude_tag = '+'.join('-' + item.strip().replace(' ', '_') for item in exclude_tag.split(','))
        
        score, count = str(score), str(count)
        base_url = "https://gelbooru.com/index.php"
        query_params = (
        f"page=dapi&s=post&q=index&tags=sort%3arandom+"
        f"{exclude_tag}+{OR_tags}+{AND_tags}"
        f"+score%3a>{score}&api_key={api_key}&user_id={user_id}&limit={count}&json=1"
        )
        url = f"{base_url}?{query_params}"
        url=url.replace("-+", "")

        posts = requests.get(url).json()['post']

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
}
