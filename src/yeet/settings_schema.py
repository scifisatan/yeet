from yeet.settings import SchemaDict

SCHEMA: list[SchemaDict] = [
    {
        "key": "ui",
        "title": "User interface settings",
        "help": "Customize the look and feel of the git client.",
        "type": "object",
        "fields": [
            {
                "key": "theme",
                "title": "Theme",
                "help": "One of Textual's built-in themes.",
                "type": "choices",
                "default": "dracula",
                "choices": [
                    "atom-one-dark",
                    "atom-one-light",
                    "catppuccin-latte",
                    "catppuccin-mocha",
                    "dracula",
                    "flexoki",
                    "gruvbox",
                    "monokai",
                    "nord",
                    "solarized-light",
                    "solarized-dark",
                    "textual-dark",
                    "textual-light",
                    "tokyo-night",
                    "rose-pine",
                    "rose-pine-moon",
                    "rose-pine-dawn",
                ],
            },
            {
                "key": "footer",
                "title": "Show footer",
                "help": "Hide footer to gain more vertical space.",
                "type": "boolean",
                "default": True,
            },
            {
                "key": "auto_copy",
                "title": "Auto-copy selected text",
                "help": "Automatically copy selected text to the clipboard.",
                "type": "boolean",
                "default": True,
            },
        ],
    },
    {
        "key": "diff",
        "title": "Diff view settings",
        "help": "Customize how diffs are rendered.",
        "type": "object",
        "fields": [
            {
                "key": "view",
                "title": "Display preference",
                "default": "auto",
                "type": "choices",
                "choices": [
                    ("Unified", "unified"),
                    ("Split", "split"),
                    ("Best fit", "auto"),
                ],
            }
        ],
    },
]
