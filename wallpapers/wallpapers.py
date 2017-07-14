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

    def get_item_text(self, menu, index, page):
        return "{number} - {title}".format(
            number=(page - 1) * len(menu['options']) + index + 1,
            title=menu['options'][index]['title']
        )

    def download(self, url, filepath, menu, getin, curr_page):
        with open(filepath, 'wb') as handle:
            res = requests.get(url, stream=True)
            i = 0
            total_length = int(res.headers.get('content-length'))
            for block in res.iter_content(WallpaperDL.DOWNLOAD_CHUNK):
                if not block:
                    break
                text = "{text} ({percent:.0f}%)".format(
                    text=self.get_item_text(menu, getin, curr_page),
                    percent=i * 1.0 * WallpaperDL.DOWNLOAD_CHUNK / total_length * 100
                )
                self.screen.addstr(getin + 9, 4, text, self.n_color)
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

    def get_menu_data(self, page):
        parsed = self.get_parsed_wps(
            'https://interfacelift.com/wallpaper/downloads/date/widescreen/{}/index{}.html'.format(
                config[RESOLUTION], page
            )
        )
        return self.get_menu('Download Wallpaper', 'Wallpapers', map(self.generate_parsed_command, parsed))

    def runmenu(self, menu, parent, pos, page):
        optioncount = len(menu['options'])  # how many options in this menu

        oldpos = None

        # Loop until return key is pressed
        while True:
            if pos != oldpos:
                oldpos = pos
                self.screen.border(0)
                self.screen.addstr(2, 2, menu['title'], curses.A_STANDOUT)
                self.screen.addstr(4, 2, 'Resolution: \'{}\', Saving in: \'{}\''.format(config[RESOLUTION],
                                                                                   config[WP_DIR]),
                              curses.A_BOLD)
                self.screen.addstr(6, 2, WallpaperDL.INSTRUCTIONS)
                self.screen.addstr(8, 2, 'Page {} - {}'.format(page, menu['subtitle']), curses.A_BOLD)

                # Display all the menu items, showing the 'pos' item highlighted
                for index in range(optioncount):
                    textstyle = self.h_color if pos == index else self.n_color
                    self.screen.addstr(9 + index, 4, self.get_item_text(menu, index, page), textstyle)
                    self.screen.clrtoeol()
                    self.screen.refresh()

            x = self.screen.getch()  # Gets user input

            # What is user input?
            if x == 258:  # down arrow
                pos = (pos + 1) % optioncount
            elif x == 259:  # up arrow
                pos = (pos - 1) % optioncount
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

        return pos, status

    def processmenu(self, menu, parent=None):
        getin = 0
        curr_page = WallpaperDL.INITIAL_PAGE
        while True:
            getin, status = self.runmenu(menu, parent, getin, curr_page)
            if status == WallpaperDL.ST_EXIT:
                break
            elif status == WallpaperDL.ST_PREV:
                if curr_page > WallpaperDL.INITIAL_PAGE:
                    curr_page -= 1
                    menu = self.get_menu_data(curr_page)
            elif status == WallpaperDL.ST_NEXT:
                curr_page += 1
                menu = self.get_menu_data(curr_page)
            elif status == WallpaperDL.ST_EXEC:
                dl_url = menu['options'][getin]['url']
                dl_path = menu['options'][getin]['dl_path']
                if menu['options'][getin]['title'].endswith(WallpaperDL.SAVED_TEXT):
                    call("open -a Preview {}".format(dl_path).split(' '))
                else:
                    self.download(dl_url, dl_path, menu, getin, curr_page)
                    menu['options'][getin]['title'] += WallpaperDL.SAVED_TEXT
            elif status == WallpaperDL.ST_DEL:
                dl_path = menu['options'][getin]['dl_path']
                if menu['options'][getin]['title'].endswith(WallpaperDL.SAVED_TEXT):
                    os.remove(dl_path)
                    menu['options'][getin]['title'] = menu['options'][getin]['title'][:-len(WallpaperDL.SAVED_TEXT)]


def main():
    wallpaper_cli = WallpaperDL()
    wallpaper_cli.processmenu(wallpaper_cli.get_menu_data(wallpaper_cli.INITIAL_PAGE))
    curses.endwin()
    os.system('clear')
