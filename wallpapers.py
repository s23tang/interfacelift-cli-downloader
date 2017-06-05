import re
import requests
import yaml
import sys
from bs4 import BeautifulSoup
from time import sleep
from subprocess import call
import curses, os

CONFIG_LOCATION = os.path.expanduser('~/.wpconfig')

config = {}
if os.path.isfile(CONFIG_LOCATION):
    with open(CONFIG_LOCATION) as config_file:
        config = yaml.load(config_file)

RESOLUTION = 'resolution'
WP_DIR = 'dir'

if RESOLUTION not in config:
    config[RESOLUTION] = '3360x2100'
if WP_DIR not in config:
    config[WP_DIR] = '~/'

config[WP_DIR] = os.path.expanduser(config[WP_DIR])

screen = curses.initscr() #initializes a new window for capturing key presses
curses.noecho() # Disables automatic echoing of key presses (prevents program from input each key twice)
curses.cbreak() # Disables line buffering (runs each key as it is pressed rather than waiting for the return key to pressed)
curses.start_color() # Lets you use colors when highlighting selected menu option
screen.keypad(1) # Capture input from keypad
curses.curs_set(0)

# Change this to use different colors when highlighting
curses.init_pair(1,curses.COLOR_BLACK, curses.COLOR_WHITE) # Sets up color pair #1, it does black text with white background
h = curses.color_pair(1) #h is the coloring for a highlighted menu option
n = curses.A_NORMAL #n is the coloring for a non highlighted menu option

MENU = "menu"
COMMAND = "command"
ST_EXIT = 'exit'
ST_PREV = 'prev'
ST_NEXT = 'next'
ST_DEL = 'delete'
ST_EXEC = 'exec'
DOMAIN = 'https://interfacelift.com'
SAVED_TEXT = ' (saved)'
DOWNLOAD_CHUNK = 512*1024
INITIAL_PAGE = 1

def get_command(title, command):
    return { 'title': title, 'type': COMMAND , 'command': command }

def get_menu(title, subtitle, options):
    return { 'title': title, 'type': MENU, 'subtitle': subtitle, 'options': options}

def parse_container(wp_container):
    return {
        'title': wp_container.find('h1').find('a').text,
        'url': wp_container.find('div', id=re.compile('^download_')).find('a')['href']
    }

def get_parsed_wps(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    wp_containers = soup.find_all('div', id=re.compile('^list_'))
    return map(parse_container, wp_containers)

def download(url, filepath, menu, getin, curr_page):
    with open(filepath, 'wb') as handle:
        res = requests.get(url, stream=True)
        i = 0
        total_length = int(res.headers.get('content-length'))
        for block in res.iter_content(DOWNLOAD_CHUNK):
            if not block:
                break
            text = "{text} ({percent:.0f}%)".format(
                text=get_item_text(menu, getin, curr_page),
                percent=i*1.0*DOWNLOAD_CHUNK/total_length*100
            )
            screen.addstr(getin+9,4, text, n)
            screen.refresh()
            i += 1
            handle.write(block)

def generate_parsed_command(parsed_item):
    dl_path = os.path.join(config[WP_DIR], parsed_item['url'].split('/')[-1])
    text = '{}{}'.format(parsed_item['title'], SAVED_TEXT if os.path.isfile(dl_path) else '')
    return { 'title': text, 'type': COMMAND, 'url': DOMAIN + parsed_item['url'], 'dl_path': dl_path}

def get_menu_data(page):
    parsed = get_parsed_wps('https://interfacelift.com/wallpaper/downloads/date/widescreen/{}/index{}.html'.format(config[RESOLUTION], page))
    return get_menu('Download Wallpaper', 'Wallpapers', map(generate_parsed_command, parsed))

def get_item_text(menu, index, page):
    return "{number} - {title}".format(
        number = (page-1) * len(menu['options']) + index + 1,
        title = menu['options'][index]['title']
    )

# This function displays the appropriate menu and returns the option selected
def runmenu(menu, parent, pos, page):
    optioncount = len(menu['options']) # how many options in this menu

    oldpos = None
    status = None
    x = None

    # Loop until return key is pressed
    while True:
        if pos != oldpos:
            oldpos = pos
            screen.border(0)
            screen.addstr(2,2, menu['title'], curses.A_STANDOUT)
            screen.addstr(4,2, 'Resolution: \'{}\', Saving in: \'{}\''.format(config[RESOLUTION], config[WP_DIR]), curses.A_BOLD)
            screen.addstr(6, 2, 'Controls: \'UP DOWN\' change rows, \'LEFT RIGHT\' change pages, \'ENTER\' to save/preview, \'BACKSPACE\' to delete')
            screen.addstr(8,2, 'Page {} - {}'.format(page, menu['subtitle']), curses.A_BOLD)

            # Display all the menu items, showing the 'pos' item highlighted
            for index in range(optioncount):
                textstyle = h if pos == index else n
                screen.addstr(9+index,4, get_item_text(menu, index, page), textstyle)
                screen.clrtoeol()
                screen.refresh()

        x = screen.getch() # Gets user input

        # What is user input?
        if x == 258: # down arrow
            pos = (pos + 1) % optioncount
        elif x == 259: # up arrow
            pos =  (pos - 1) % optioncount
        elif x == 260: # left arrow
            status = ST_PREV
            break
        elif x == 261: # right arrow
            status = ST_NEXT
            break
        elif x == ord('\n'):
            status = ST_EXEC
            break
        elif x == ord('q') or x == 27: # q or esc pressed
            status = ST_EXIT
            break
        elif x == 127:
            status = ST_DEL
            break

    return pos, status

# This function calls showmenu and then acts on the selected item
def processmenu(menu, parent=None):
    optioncount = len(menu['options'])
    getin = 0
    curr_page = INITIAL_PAGE
    while True:
        getin, status = runmenu(menu, parent, getin, curr_page)
        if status == ST_EXIT:
            break
        elif status == ST_PREV:
            if curr_page > INITIAL_PAGE:
                curr_page -= 1
                menu = get_menu_data(curr_page)
        elif status == ST_NEXT:
            curr_page += 1
            menu = get_menu_data(curr_page)
        elif status == ST_EXEC:
            dl_url = menu['options'][getin]['url']
            dl_path = menu['options'][getin]['dl_path']
            if menu['options'][getin]['title'].endswith(SAVED_TEXT):
                call("open -a Preview {}".format(dl_path).split(' '))
            else:
                download(dl_url, dl_path, menu, getin, curr_page)
                menu['options'][getin]['title'] += SAVED_TEXT
        elif status == ST_DEL:
            dl_path = menu['options'][getin]['dl_path']
            if menu['options'][getin]['title'].endswith(SAVED_TEXT):
                os.remove(dl_path)
                menu['options'][getin]['title'] = menu['options'][getin]['title'][:-len(SAVED_TEXT)]

# Main program
processmenu(get_menu_data(INITIAL_PAGE))
curses.endwin() #VITAL! This closes out the menu system and returns you to the bash prompt.
os.system('clear')
