import requests
import json
from PIL import Image, ImageOps
import re
import requests
import base64
import io
import numpy as np
from PIL import Image, ImageOps
import torch
import boto3
import comfy


#urls to image from https://github.com/wmatson/easy-comfy-nodes/blob/main/__init__.py#L140
def loadImageFromUrl(url):
    if url.startswith("data:image/"):
        i = Image.open(io.BytesIO(base64.b64decode(url.split(",")[1])))
    elif url.startswith("s3://"):
        s3 = boto3.client('s3')
        bucket, key = url.split("s3://")[1].split("/", 1)
        obj = s3.get_object(Bucket=bucket, Key=key)
        i = Image.open(io.BytesIO(obj['Body'].read()))
    else:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            raise Exception(response.text)

        i = Image.open(io.BytesIO(response.content))

    i = ImageOps.exif_transpose(i)

    if i.mode != "RGBA":
        i = i.convert("RGBA")

    # recreate image to fix weird RGB image
    alpha = i.split()[-1]
    image = Image.new("RGB", i.size, (0, 0, 0))
    image.paste(i, mask=alpha)

    image = np.array(image).astype(np.float32) / 255.0
    image = torch.from_numpy(image)[None,]
    if "A" in i.getbands():
        mask = np.array(i.getchannel("A")).astype(np.float32) / 255.0
        mask = 1.0 - torch.from_numpy(mask)
    else:
        mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

    return (image, mask)

class UrlsToImage:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"urls": ("STRING", {"default": "", "multiline": True, "dynamicPrompts": False})}}
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES=("images",)
    FUNCTION = "execute"
    CATEGORY = "Gelbooru"

    def execute(self, urls):
        print(urls.split("\n"))
        images = [loadImageFromUrl(u)[0] for u in urls.split("\n")]
        firstImage = images[0]
        restImages = images[1:]
        if len(restImages) == 0:
            return (firstImage,)
        else:
            image1 = firstImage
            for image2 in restImages:
                if image1.shape[1:] != image2.shape[1:]:
                    image2 = comfy.utils.common_upscale(image2.movedim(-1, 1), image1.shape[2], image1.shape[1], "bilinear", "center").movedim(1, -1)
                image1 = torch.cat((image1, image2), dim=0)
            return (image1,)


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
    "UrlsToImage": "UrlsToImage",
}
