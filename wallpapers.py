import re
import requests
import yaml
import sys
from bs4 import BeautifulSoup
from time import sleep
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
EXIT_POS = -1
PREV_PAGE = -2
NEXT_PAGE = -3
DOMAIN = 'https://interfacelift.com'
SAVED_TEXT = ' (saved)'

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

def download(url, filepath):
    with open(filepath, 'wb') as handle:
        res = requests.get(url, stream=True)
        for block in res.iter_content(1024):
            if not block:
                break
            handle.write(block)

def generate_parsed_command(parsed_item):
    dl_path = os.path.join(config[WP_DIR], parsed_item['url'].split('/')[-1])
    text = '{}{}'.format(parsed_item['title'], SAVED_TEXT if os.path.isfile(dl_path) else '')
    return { 'title': text, 'type': COMMAND, 'url': DOMAIN + parsed_item['url'], 'dl_path': dl_path}

def get_menu_data(page):
    parsed = get_parsed_wps('https://interfacelift.com/wallpaper/downloads/date/widescreen/{}/index{}.html'.format(config[RESOLUTION], page))
    return get_menu('Download Wallpaper', 'Wallpapers', map(generate_parsed_command, parsed))

# This function displays the appropriate menu and returns the option selected
def runmenu(menu, parent, pos, page):
  optioncount = len(menu['options']) # how many options in this menu

  oldpos=None # used to prevent the screen being redrawn every time
  x = None #control for while loop, let's you scroll through options until return key is pressed then returns pos to program

  # Loop until return key is pressed
  while x !=ord('\n'):
    if pos != oldpos:
      oldpos = pos
      screen.border(0)
      screen.addstr(2,2, menu['title'], curses.A_STANDOUT) # Title for this menu
      screen.addstr(4,2, 'Resolution: \'{}\', Saving in: \'{}\''.format(config[RESOLUTION], config[WP_DIR]), curses.A_BOLD)
      screen.addstr(6,2, 'Page {} - {}'.format(page, menu['subtitle']), curses.A_BOLD) #Subtitle for this menu

      # Display all the menu items, showing the 'pos' item highlighted
      for index in range(optioncount):
        textstyle = h if pos == index else n
        text = "{number} - {title}".format(
            number = (page-1) * optioncount + index + 1,
            title = menu['options'][index]['title']
        )
        screen.addstr(7+index,4, text, textstyle)
        screen.clrtoeol()
      screen.refresh()

    x = screen.getch() # Gets user input

    # What is user input?
    if x == 113 or x == 27: # q or esc pressed
      pos = EXIT_POS
      break
    elif x == 258: # down arrow
      pos = (pos + 1) % optioncount
    elif x == 259: # up arrow
      pos =  (pos - 1) % optioncount
    elif x == 260: # left arrow
      pos = PREV_PAGE
      break
    elif x == 261: # right arrow
      pos = NEXT_PAGE
      break

  # return index of the selected item
  return pos

INITIAL_PAGE = 1

# This function calls showmenu and then acts on the selected item
def processmenu(menu, parent=None):
  optioncount = len(menu['options'])
  exitmenu = False
  getin = 0
  curr_page = INITIAL_PAGE
  while not exitmenu: #Loop until the user exits the menu
    getin = runmenu(menu, parent, getin, curr_page)
    if getin == EXIT_POS:
        exitmenu = True
    elif getin == PREV_PAGE:
        if curr_page > INITIAL_PAGE:
            curr_page -= 1
            menu = get_menu_data(curr_page)
    elif getin == NEXT_PAGE:
        curr_page += 1
        menu = get_menu_data(curr_page)
    elif menu['options'][getin]['type'] == COMMAND:
      dl_url = menu['options'][getin]['url']
      dl_path = menu['options'][getin]['dl_path']
      if menu['options'][getin]['title'].endswith(SAVED_TEXT):
        os.remove(dl_path)
        menu['options'][getin]['title'] = menu['options'][getin]['title'][:-len(SAVED_TEXT)]
      else:
        download(dl_url, dl_path)
        menu['options'][getin]['title'] += SAVED_TEXT
    elif menu['options'][getin]['type'] == MENU:
          screen.clear() #clears previous screen on key press and updates display based on pos
          processmenu(menu['options'][getin], menu) # display the submenu
          screen.clear() #clears previous screen on key press and updates display based on pos

# Main program
processmenu(get_menu_data(INITIAL_PAGE))
curses.endwin() #VITAL! This closes out the menu system and returns you to the bash prompt.
os.system('clear')
