import json
import re
import requests

from tqdm import tqdm


def get_instagram_shared_data(text):
    """
    Given a Instagram HTML page, return the
    'shared_data' json object
    """
    json_blob = re.findall(r"window._sharedData\s=\s(.+);</script>", text)[0]
    return json.loads(json_blob)


def get_username_from_shortcode(shortcode):
    """
    Given a shortcode (e.g. 'BUwTJMRgKKD'), try and
    find op's username (in order to get their profile page)
    """
    shortcode_url = 'https://www.instagram.com/p/{}/'.format(shortcode)

    r = requests.get(shortcode_url)
    r_js = get_instagram_shared_data(r.text)
    username = r_js['entry_data']['PostPage'][0]['graphql']['shortcode_media']['owner']['username']
    return username


def get_profile_next_end_cursor(profile_id, end_cursor):
    """
    Given the next endcursor, retrieve the list
    of profile pic URLS and if 'has_next_page'
    """
    next_url = "https://www.instagram.com/graphql/query/" \
               "?query_id=17880160963012870&id={}&first=12&after={}".format(
                   profile_id, end_cursor
               )

    r = requests.get(next_url)
    r_json = json.loads(r.text)

    # Gets next page info
    edge_timeline_media = r_json['data']['user']['edge_owner_to_timeline_media']
    page_info = edge_timeline_media['page_info']
    has_next_page, end_cursor = page_info['has_next_page'], page_info['end_cursor']

    # Accumulates all display pictures here
    display_pictures = []
    for i in edge_timeline_media['edges']:
        display_pictures.append(i['node']['display_url'])

    return display_pictures, has_next_page, end_cursor


def get_instagram_profile_display_pictures(profile_id, username, num_pics=72):
    """
    Given an instagram username, traverse their profile
    and scrap <num_pics> of their display pictures
    """
    # Total display images scraped
    total_display_images = []

    r = requests.get('https://www.instagram.com/{}/'.format(username))
    r_js = get_instagram_shared_data(r.text)
    media_json = r_js['entry_data']['ProfilePage'][0]['user']['media']

    # Get the first 12 display pictures
    #
    for pic in media_json['nodes']:
        total_display_images.append(pic['display_src'])

    # Next N pictures are a bit different
    end_cursor = media_json['page_info']['end_cursor']
    has_next_page = media_json['page_info']['has_next_page']

    # Only want to scrap entire feed, just want
    # 81 photos (12 initial + 60 traversed)
    i_max = int((num_pics - 12) / 12)
    for i in tqdm(range(i_max), desc='{} feed'.format(username)):
        display_images, has_next_page, end_cursor \
            = get_profile_next_end_cursor(profile_id, end_cursor)
        total_display_images.extend(display_images)

        if not has_next_page:
            break

    return total_display_images


def get_instagram_hashtag_feed(has_next_page, end_cursor, tags='selfie'):
    """
    Traverses through instagram's hashtag feed, using the
    graphql endpoint
    """
    feed_url = 'https://www.instagram.com/graphql/query/?query_id=17882293912014529&' \
               'tag_name={}&first=9&after={}'.format(tags, end_cursor)

    r = requests.get(feed_url)
    r_js = json.loads(r.text)

    # Has next page or nah
    page_info = r_js['data']['hashtag']['edge_hashtag_to_media']['page_info']
    has_next_page, end_cursor = page_info['has_next_page'], page_info['end_cursor']

    edges = r_js['data']['hashtag']['edge_hashtag_to_top_posts']['edges']

    usernames = []
    profile_ids = []
    for i in edges:
        profile_ids.append(i['node']['owner']['id'])
        usernames.append(
            get_username_from_shortcode(i['node']['shortcode'])
        )

    return list(zip(usernames, profile_ids)), has_next_page, end_cursor


def instagram_hashtag_seed(tags='selfie'):
    """
    Seed function that calls instagram's hashtag page
    in order to obtain the end_cursor thingo
    """
    r=requests.get('https://www.instagram.com/explore/tags/{}/'.format(tags))
    r_js=get_instagram_shared_data(r.text)

    usernames=[]
    profile_ids=[]

    # Fb works by firstly calling the first page
    # and loading the HTML and all that jazz, so
    # you need to parse that bit during the 1st call.
    # The proceeding images can be obtained by
    # calling the graphql api endpoint with a
    # specified end_cursor
    media_json=r_js['entry_data']['TagPage'][0]['tag']['media']
    for i in media_json['nodes']:
        profile_ids.append(i['owner']['id'])
        usernames.append(get_username_from_shortcode(i['code']))

    page_info=media_json['page_info']
    has_next_page, end_cursor=page_info['has_next_page'], page_info['end_cursor']

    return list(zip(usernames, profile_ids)), has_next_page, end_cursor