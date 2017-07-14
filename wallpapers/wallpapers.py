#-*- coding: utf-8 -*-
import re
import requests
import yaml
from bs4 import BeautifulSoup
from subprocess import call
import curses, os
import locale

locale.setlocale(locale.LC_ALL, '')

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


class WallpaperDL:
    MENU = "menu"
    COMMAND = "command"
    ST_EXIT = 'exit'
    ST_PREV = 'prev'
    ST_NEXT = 'next'
    ST_DEL = 'delete'
    ST_EXEC = 'exec'
    DOMAIN = 'https://interfacelift.com'
    SAVED_TEXT = ' (saved)'
    DOWNLOAD_CHUNK = 512 * 1024
    INITIAL_PAGE = 1
    INSTRUCTIONS = 'Controls: \'↑ ↓ ← →\' rows/pages, \'ENTER\' save/preview, \'BACKSPACE\' delete, \'Q/ESC\' quit'

    def __init__(self):
        # Screen and curses setup
        self.screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.start_color()
        self.screen.keypad(1)
        curses.curs_set(0)

        # Colors on screen
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        self.h_color = curses.color_pair(1)
        self.n_color = curses.A_NORMAL

        # Menu data
        self.curr_pos = 0
        self.curr_page = WallpaperDL.INITIAL_PAGE
        self.menu_data = self.get_menu_data()

        # Start running
        self.run()

        # Stop if exit
        curses.endwin()
        os.system('clear')

    def get_command(self, title, command):
        return {'title': title, 'type': WallpaperDL.COMMAND, 'command': command}

    def get_menu(self, title, subtitle, options):
        return { 'title': title, 'type': WallpaperDL.MENU, 'subtitle': subtitle, 'options': options}

    def parse_container(self, wp_container):
        return {
            'title': wp_container.find('h1').find('a').text,
            'url': wp_container.find('div', id=re.compile('^download_')).find('a')['href']
        }

    def get_parsed_wps(self, url):
        page = requests.get(url)
        soup = BeautifulSoup(page.content, 'html.parser')
        wp_containers = soup.find_all('div', id=re.compile('^list_'))
        return map(self.parse_container, wp_containers)

    def get_item_text(self, index):
        return "{number} - {title}".format(
            number=(self.curr_page - 1) * len(self.menu_data['options']) + index + 1,
            title=self.menu_data['options'][index]['title']
        )

    def download(self, url, filepath):
        with open(filepath, 'wb') as handle:
            res = requests.get(url, stream=True)
            i = 0
            total_length = int(res.headers.get('content-length'))
            for block in res.iter_content(WallpaperDL.DOWNLOAD_CHUNK):
                if not block:
                    break
                text = "{text} ({percent:.0f}%)".format(
                    text=self.get_item_text(self.curr_pos),
                    percent=i * 1.0 * WallpaperDL.DOWNLOAD_CHUNK / total_length * 100
                )
                self.screen.addstr(self.curr_pos + 9, 4, text, self.n_color)
                self.screen.refresh()
                i += 1
                handle.write(block)

    def generate_parsed_command(self, parsed_item):
        dl_path = os.path.join(config[WP_DIR], parsed_item['url'].split('/')[-1])
        text = '{}{}'.format(parsed_item['title'].encode('utf-8'),
                             WallpaperDL.SAVED_TEXT if os.path.isfile(dl_path) else '')
        return {
            'title': text,
            'type': WallpaperDL.COMMAND,
            'url': WallpaperDL.DOMAIN + parsed_item['url'],
            'dl_path': dl_path
        }

    def get_menu_data(self):
        parsed = self.get_parsed_wps(
            'https://interfacelift.com/wallpaper/downloads/date/widescreen/{}/index{}.html'.format(
                config[RESOLUTION], self.curr_page
            )
        )
        return self.get_menu('Download Wallpaper', 'Wallpapers', map(self.generate_parsed_command, parsed))

    def run_menu(self):
        option_count = len(self.menu_data['options'])  # how many options in this menu
        old_pos = None
        # Loop until return key is pressed
        while True:
            if self.curr_pos != old_pos:
                old_pos = self.curr_pos
                self.screen.border(0)
                self.screen.addstr(2, 2, self.menu_data['title'], curses.A_STANDOUT)
                self.screen.addstr(4, 2, 'Resolution: \'{}\', Saving in: \'{}\''.format(
                    config[RESOLUTION],
                    config[WP_DIR]
                ), curses.A_BOLD)
                self.screen.addstr(6, 2, WallpaperDL.INSTRUCTIONS)
                self.screen.addstr(8, 2, 'Page {} - {}'.format(
                    self.curr_page,
                    self.menu_data['subtitle']
                ), curses.A_BOLD)

                # Display all the menu items, showing the 'pos' item highlighted
                for index in range(option_count):
                    textstyle = self.h_color if self.curr_pos == index else self.n_color
                    self.screen.addstr(9+index, 4, self.get_item_text(index), textstyle)
                    self.screen.clrtoeol()
                    self.screen.refresh()

            x = self.screen.getch()  # Gets user input

            # What is user input?
            if x == 258:  # down arrow
                self.curr_pos = (self.curr_pos + 1) % option_count
            elif x == 259:  # up arrow
                self.curr_pos = (self.curr_pos - 1) % option_count
            elif x == 260:  # left arrow
                status = WallpaperDL.ST_PREV
                break
            elif x == 261:  # right arrow
                status = WallpaperDL.ST_NEXT
                break
            elif x == ord('\n'):
                status = WallpaperDL.ST_EXEC
                break
            elif x == ord('q') or x == 27:  # q or esc pressed
                status = WallpaperDL.ST_EXIT
                break
            elif x == 127:
                status = WallpaperDL.ST_DEL
                break

        return status

    def run(self):
        while True:
            status = self.run_menu()
            if status == WallpaperDL.ST_EXIT:
                break
            elif status == WallpaperDL.ST_PREV:
                if self.curr_page > WallpaperDL.INITIAL_PAGE:
                    self.curr_page -= 1
                    self.menu_data = self.get_menu_data()
            elif status == WallpaperDL.ST_NEXT:
                self.curr_page += 1
                self.menu_data = self.get_menu_data()
            else:
                menu_link = self.menu_data['options'][self.curr_pos]
                dl_path = menu_link['dl_path']
                if status == WallpaperDL.ST_EXEC:
                    dl_url = menu_link['url']
                    if menu_link['title'].endswith(WallpaperDL.SAVED_TEXT):
                        call('open -a Preview {}'.format(dl_path).split(' '))
                    else:
                        self.download(dl_url, dl_path)
                        menu_link['title'] += WallpaperDL.SAVED_TEXT
                elif status == WallpaperDL.ST_DEL and menu_link['title'].endswith(WallpaperDL.SAVED_TEXT):
                    os.remove(dl_path)
                    menu_link['title'] = menu_link['title'][:-len(WallpaperDL.SAVED_TEXT)]


def main():
    # Run wallpaper cli
    WallpaperDL()
