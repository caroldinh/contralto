from bs4 import BeautifulSoup
import requests
import statistics

def analyze(artist, individual=False):

    artist = artist.replace("/", "%2F")

    artist_page = "https://www.last.fm/music/" + artist + "/+wiki"
    page = requests.get(artist_page)
    soup = BeautifulSoup(page.content, "html.parser")

    content = soup.find(class_="wiki-content")
    no_data = soup.find(class_="no-data-message")
    
    if(content == None or no_data != None):
        return "Undetermined"
    content = content.find_all("p")
    paragraph_count = 0
    bio_short = ""
    while len(bio_short) < 2500 and paragraph_count < len(content):
        bio_short += content[paragraph_count].text.lower() + " "
        paragraph_count += 1

    content = content[:paragraph_count]
    # print(bio_short)

    masc_indicators = ['he', 'him', 'his', 'himself', 'frontman', 'boy']
    fem_indicators = ['she', 'her', 'hers', 'herself', 'female', 'female-fronted', 'frontwoman', 'girl']
    nonbinary_indicators = ['they', 'them', 'theirs', 'their', 'themself', 'they/them', 'non-binary', 'nonbinary']

    bio_words = bio_short.split()

    masc_count = 0
    fem_count = 0
    neutral_count = 0
    isGroup = False

    factbox = soup.find(class_="factbox")
    factbox_items = None
    members_list = None
    if(factbox != None):
        factbox_items = factbox.find_all(class_="factbox-item")
        for item in factbox_items:
            heading = item.find(class_="factbox-heading")
            if(heading != None and heading.text == "Members"):
                isGroup = True
                members_list = item

    for indicator in masc_indicators:
        masc_count += bio_words.count(indicator)

    for indicator in fem_indicators:
        fem_count += bio_words.count(indicator)

    for indicator in nonbinary_indicators:
        neutral_count += bio_words.count(indicator)

    if("was formed" in bio_short or "formed in" in bio_short or "consists of" in bio_short or "consisting of" in bio_short):
        isGroup = True

    if(individual):
        isGroup = False

    if(isGroup):
        tags_analysis = analyze_based_on_tags(artist)
        if(tags_analysis == "Undetermined"):
            if(members_list != None):
                members = members_list.find_all("li")
                member_searches = []
                for member in members:
                    member_name = member.find("span").text
                    result = analyze(member_name, individual=True)
                    if(result != "Undetermined"):
                        member_searches.append(result)
                unique = set(member_searches)
                if(len(unique) > 0):
                    if(len(unique) > 2):
                        return "Mixed-gender"
                    else:
                        return unique.pop()
                else:
                    return "Undetermined"
        else:
            return tags_analysis

    if("frontman" in bio_short or "boy band" in bio_short or \
        (masc_count > fem_count and masc_count > neutral_count)):
        return "Male or male-fronted"
    
    elif("frontwoman" in bio_short or "female-fronted" in bio_short or "girl group" in bio_short or "all-girl" in bio_short or \
        (fem_count > masc_count and fem_count > neutral_count)):
        return "Female or female-fronted"

    # This line basically indicates that they are non-binary/gnc
    elif(("nonbinary" in bio_short or "non-binary" in bio_short or "they/them" in bio_short) or \
        (neutral_count > masc_count and neutral_count > fem_count)):
        return "Nonbinary or nonbinary-fronted"
    
    else:
        return analyze_based_on_tags(artist)

def analyze_based_on_tags(artist):
    
    artist_page = "https://www.last.fm/music/" + artist + "/+tags"
    page = requests.get(artist_page)
    soup = BeautifulSoup(page.content, "html.parser")

    tags = soup.find_all(class_="big-tags-item")
    for tag in tags:
        tag_name = tag.find(class_="link-block-target").text
        if(tag_name.lower() == "female vocalists" or tag_name.lower() == "girl group"):
            return "Female or female-fronted"
        elif(tag_name.lower() == "male vocalists" or tag_name.lower() == "boy band"):
            return "Male or male-fronted"
    
    return "Undetermined"