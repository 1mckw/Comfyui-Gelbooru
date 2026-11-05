# ComfyUI-Gelbooru

![screenshot.jpg](screenshot.jpg)

A set of custom nodes for ComfyUI that fetch random images from [Gelbooru](https://gelbooru.com/) and [Rule34](https://rule34.xxx/) based on tag filters, post ID, or direct URL. It also ships a **Tag Rules** node that rewrites and filters the fetched tags before they reach your prompt.

https://github.com/user-attachments/assets/e07b95f2-61e6-4d52-9d36-7eade996e720

## Installation

1. Navigate to your `ComfyUI/custom_nodes` folder
2. `git clone https://github.com/1mckw/Comfyui-Gelbooru.git`
3. From the ComfyUI root directory, install dependencies:

   ```
   python_embeded\python.exe -m pip install -r custom_nodes\Comfyui-Gelbooru\requirements.txt
   ```
4. Restart ComfyUI

## Getting API Credentials

Gelbooru **requires** an API key and user ID to fetch posts.

1. Go to https://gelbooru.com/index.php?page=account&s=options
2. Scroll to the bottom of the page
3. Copy your `api_key` and `user_id`
4. Enter them in the `api_credentials` field in this format:

```
api_key=YOUR_API_KEY&user_id=YOUR_USER_ID
```

---

## Nodes

### Gelbooru (Random)

Fetches random image posts from Gelbooru or Rule34 based on your tag filters.

| Field | Description |
|---|---|
| `site` | Image board to search: `Gelbooru` or `Rule34` |
| `OR_tags` | At least one of these tags must be present (broadens results). Comma-separated. |
| `AND_tags` | Every one of these tags must be present on the image (narrows results). Comma-separated. |
| `exclude_tag` | Tags to exclude from search results. Comma-separated. Default: `animated` to skip GIFs/videos. |
| `remove_tags` | Tags to strip from the output `imgtags`. Comma-separated. Default: `censored, mosaic_censoring, bar_censor`. |
| `add_good_tags` | Prepend quality tags (`masterpiece, best quality, amazing quality, very aesthetic`) loaded from `good_tags.txt`. `True` by default. |
| `remove_bad_tags` | Remove known bad tags (watermark, text, censored, signature, etc.) loaded from `bad_tags.txt`. `True` by default. |
| `convert_underscore` | Replace underscores (`_`) with spaces in the output tags. `False` by default. |
| `change_background` | Add or remove background-related tags. Options: `Don't Change`, `Add Background`, `Remove Background`, `Remove All`. |
| `change_color` | Add or remove color-related tags. Options: `Don't Change`, `Colored`, `Limited Palette`, `Monochrome`. |
| `Safe` | Include Safe/General rated posts |
| `Questionable` | Include Questionable/Sensitive rated posts |
| `Explicit` | Include Explicit rated posts |
| `score` | Minimum score threshold. `0` = no filter. |
| `api_credentials` | Your API key and user ID in format `api_key=xxx&user_id=xxx` |
| `seed` | Seed for deterministic random selection. `0` = truly random. |
| `count` | Number of posts to fetch per request (max 100). |
| `use_last_prompt` | Reuse the previous API response without making a new request. Useful for iterating on the same batch. |
| `return_picture` | Download the first post's image and output it as an IMAGE tensor. |
| `extra_text` | (Optional) Generated text from another node. Prepended before all post tags. |

#### AND_tags vs OR_tags

Understanding these two fields is key to getting good results:

- **AND_tags** — every tag you list here **must** be on the image. Adding more tags narrows your results.
  - Example: `1girl, smile, blonde` → only images with **all three** tags
- **OR_tags** — at least **one** of the tags you list here must be present. Adding more tags broadens your results.
  - Example: `blonde, red_hair, brown_hair` → images with **any** of these hair colors

**Typical usage:**
- AND_tags: `1girl, solo` (these are mandatory)
- OR_tags: `blonde, red_hair, brown_hair` (any hair color is fine, you want variety)
- Result: a mix of blondes, redheads, and brunettes from the same batch

#### Rating Toggles

Each rating toggle controls whether that rating is **included** or **excluded**:

- **Safe = True** (default): Safe/General posts are included. Set to `False` to exclude them.
- **Questionable = True** (default): Questionable/Sensitive posts are included. Set to `False` to exclude them.
- **Explicit = True** (default): Explicit posts are included. Set to `False` to exclude them.

The API adds rating exclusion parameters based on which toggles you disable.

#### Tag Processing Pipeline

The output `imgtags` is processed in this order:

1. **`remove_tags`** — strips user-specified tags from the raw post tags
2. **`remove_bad_tags`** — filters out known bad tags loaded from `bad_tags.txt`
3. **`change_background`** — adds or removes background-related tags
4. **`change_color`** — adds or removes color-related tags
5. **`convert_underscore`** — replaces `_` with spaces
6. **`extra_text`** — prepended before the processed post tags
7. **`add_good_tags`** — prepended at the very beginning from `good_tags.txt`

**Config files** (located in the node folder):

- **`bad_tags.txt`** — comma-separated list of tags to remove when `remove_bad_tags` is enabled. Includes watermark, censored, text, signature, ai_generated, and more (57 tags by default). Edit this file to customize.
- **`good_tags.txt`** — comma-separated list of quality tags prepended when `add_good_tags` is enabled. Default: `masterpiece, best quality, amazing quality, very aesthetic`.

**Final output structure:**
```
<good_tags>
<extra_text>
<processed post tags>
```

---

### Gelbooru (ID)

Fetches a single post from Gelbooru by its numeric post ID.

| Field | Description |
|---|---|
| `post_id` | The numeric ID of the post to fetch (e.g. `1234567`). |
| `use_last_prompt` | Reuse the previous API response without making a new request. |
| `return_picture` | Download the post's image and output it as an IMAGE tensor. |

---

### Gelbooru (Tag Rules - Replace & Remove)

Rewrites the `imgtags` string coming from the Gelbooru nodes with your own rules - no code needed.
Two editable tables live inside the node:

- **Replace tags** - left column is what to find, right column is what to put instead.
- **Remove tags** - tags that must never reach the prompt (for example `censored`).

| Field | Description |
|---|---|
| `text` | Input socket. Connect `imgtags` (or any STRING) here. One post per line, tags separated by commas. |
| `match_mode` | How several tags in the **Find** column are matched (see below). |
| `case_sensitive` | `False` by default, so `1Girl` and `1girl` are treated as the same tag. |
| `treat_underscore_as_space` | `True` by default, so a rule written as `long hair` also matches the tag `long_hair`. |
| `remove_duplicates` | `True` by default, drops repeated tags from each line after the rules ran. |
| `rules_json` | Hidden field that stores the rule table as JSON. You normally never edit it by hand, but it keeps workflows and API calls portable. |

**Using the tables**

- Press **+ Add rule** under the replace table (or **+ Add tag** under the remove table) to add a row, press **✕** to delete one, and press `Enter` inside a field to add the next row.
- Both columns accept several comma separated tags:

  | Find | Replace with | Effect |
  |---|---|---|
  | `1girl` | `1boy` | one tag becomes one tag |
  | `1girl` | `1boy, male_focus` | one tag becomes two |
  | `1girl, solo` | `1boy` | two tags become one |
  | `censored` | *(empty)* | deletes the found tags |

- The **Remove** column accepts the `*` wildcard, so `*_background` removes `white_background`, `simple_background`, ...
- Rules run from top to bottom and chain into each other, then the remove table cleans up the result.

**match_mode**

- `All tags (any order)` (default) - every tag in the Find cell must be somewhere on the line, so `1girl, solo` matches `solo, 1girl, smile`.
- `Exact sequence` - the tags must sit next to each other in that order, so `1girl, solo` matches `1girl, solo, smile` but not `solo, 1girl`.

**Example**

```
imgtags : masterpiece, 1girl, solo, long_hair, censored
rule 1  : 1girl, solo  -> 1boy, male_focus
rule 2  : long hair    -> short_hair
remove  : censored
result  : masterpiece, 1boy, male_focus, short_hair
```

---

### UrlsToImage

Loads images from one or more URLs into an IMAGE tensor.

| Field | Description |
|---|---|
| `urls` | Image URLs to load, one per line. Supports `http://`, `data:image/` (base64), and `s3://` URIs. |

---

## Outputs

The `Gelbooru (Random)` and `Gelbooru (ID)` nodes share these common output sockets:

| Output | Type | Description |
|---|---|---|
| `imgtags` | STRING | All tags of the fetched post(s), comma-separated (one post per line). |
| `imgurl` | STRING | Direct file URL(s) of the image(s) (one per line). |
| `imgid` | STRING | Post ID(s) on the image board (one per line). |
| `width` | INT | Width of the image(s) in pixels. |
| `height` | INT | Height of the image(s) in pixels. |
| `source` | STRING | Source website URL(s) of the post(s) (one per line). |
| `url` | STRING | The full API query URL used for the request (Gelbooru Random only). |
| `IMAGE` | IMAGE | Image tensor — only populated when `return_picture` is enabled, otherwise a blank 1x1 image. |

---

## Pro Tip: Autocomplete

For a much smoother tagging experience, install [ComfyUI-Autocomplete-Plus](https://github.com/newtextdoc1111/ComfyUI-Autocomplete-Plus). It provides autocomplete suggestions for Gelbooru tags directly in ComfyUI text fields, making tag entry fast and error-free.
