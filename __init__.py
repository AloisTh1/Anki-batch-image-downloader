"""Add on to scrape from google image search and download it to the media folder.

Alois Thibert
alois.devlp@gmail.com

"""

import re
import time
from io import BytesIO
from typing import List

import requests
from aqt import gui_hooks
from aqt.operations import QueryOp
from aqt.qt import QApplication, QDialog
from aqt.utils import qconnect, showInfo, tooltip

from .gui.gui import Ui_Images_downloader

QApplication.instance().processEvents()


def parse_user_src_field(addon_window) -> str:
    return addon_window.combo_field_src.currentText()


def parse_user_dst_field(addon_window) -> str:
    return addon_window.combo_field_dst.currentText()


def parse_user_mode(addon_window) -> str:
    return addon_window.combo_action.currentText()


def parse_user_nb_images(addon_window) -> int:
    return int(addon_window.selector_nbImages.value())


def setup_gui_addon(browser) -> None:
    cards_id = browser.selectedNotes()
    if not cards_id:
        tooltip("Please select atleast one card")
        return

    main_window = browser.mw
    dialog = QDialog(browser)
    addon_window = Ui_Images_downloader()
    addon_window.setupUi(dialog)

    notes = []
    for card_id in cards_id:
        notes.append(main_window.col.getNote(card_id))

    fields = notes[0].keys()
    addon_window.combo_field_src.addItems(fields)
    addon_window.combo_field_dst.addItems(fields)

    dialog.setVisible(True)

    dialog.accepted.connect(
        lambda: launch_bg_note_processing(
            mw=main_window,
            notes=notes,
            addon_window=addon_window,
        )
    )


def _add_pictures_to_card(note, field, mode, file_names):

    if mode == "Overwrite":
        note[field] = ""

    for file_name in file_names:
        note[field] += "".join("<img src={}>".format(file_name))

    note.flush()


def url_to_bytes(url_list):
    buffer_list = []
    for url in url_list:
        buffer_list.append(BytesIO(requests.get(url).content))

    return buffer_list


def img_to_media_folder(mw, bytes_list, names):
    file_names = []
    for i, data in enumerate(bytes_list):
        file_names.append(mw.col.media.writeData(names[i], data.read()))
    return file_names


def on_success(_) -> None:
    showInfo("Processing has finished.")


def launch_bg_note_processing(mw, notes, addon_window):
    op = QueryOp(
        parent=mw,
        op=lambda _: update_notes(mw, notes, addon_window),
        success=on_success,
    )

    op.with_progress().run_in_background()


def update_notes(mw, notes, addon_window):
    nb_images = parse_user_nb_images(addon_window=addon_window)
    src_field = parse_user_src_field(addon_window=addon_window)
    dst_field = parse_user_dst_field(addon_window=addon_window)
    nb_notes = len(notes)
    for i, note in enumerate(notes):
        start = time.time()
        url_list = parse_pictures(query(text=note[src_field]))[:nb_images]
        pictures = url_to_bytes(url_list)
        files_names = img_to_media_folder(
            mw, pictures, [str(int(start * 10000000)) for _ in range(nb_images)]
        )

        for picture in pictures:
            picture.close()

        mw.taskman.run_on_main(
            lambda: mw.progress.update(
                label="{done}/{total} cards. {frac}cards/s. Remainining:~{timeremaining} s".format(
                    done=i,
                    total=nb_notes,
                    frac=round(1 / (time.time() - start), 2),
                    timeremaining=round((nb_notes - i) * (time.time() - start), 1),
                ),
            )
        )

        _add_pictures_to_card(
            note=note,
            field=dst_field,
            mode=parse_user_mode(addon_window=addon_window),
            file_names=files_names,
        )

    mw.requireReset()


def query(text) -> str:
    cookies = {"CONSENT": "YES+cb.20210720-07-p0.en+FX+410"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36"
    }

    params = {
        "q": text,  # search query
        "tbm": "isch",  # image results
        "content-type": "image/png",
    }

    html = requests.get(
        "https://www.google.com/search",
        params=params,
        headers=headers,
        cookies=cookies,
        timeout=30,
    )
    return html.text


def parse_pictures(soup) -> List:
    return re.findall(r"data-src=\"(.+?)\"", str(soup))


def set_up_addon_menu(browser) -> None:
    menu = browser.form.menu_Cards
    menu.addSeparator()
    menu_action = menu.addAction("Add Images")
    qconnect(menu_action.triggered, lambda _: setup_gui_addon(browser=browser))


def init():
    gui_hooks.browser_menus_did_init.append(set_up_addon_menu)


init()
