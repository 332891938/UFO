from types import SimpleNamespace


def get_ufo_config():
    system = SimpleNamespace(
        after_click_wait=0.0,
        click_api="click_input",
        input_text_inter_key_pause=0.01,
        input_text_api="type_keys",
        input_text_enter=False,
        default_png_compress_level=6,
        annotation_colors={
            "Button": "red",
            "Edit": "blue",
            "Text": "green",
            "MenuItem": "orange",
            "default": "yellow",
        },
        annotation_font_size=16,
    )
    return SimpleNamespace(system=system)
