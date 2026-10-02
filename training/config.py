"""Load JSON training defaults, with explicit CLI arguments taking precedence."""

import json
import sys
from pathlib import Path


def parse_args(parser, argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser.add_argument("--config", type=Path, help="JSON defaults; CLI arguments override")
    path = parser.parse_known_args(argv)[0].config
    defaults = []
    if path:
        values = json.loads(path.read_text())
        if not isinstance(values, dict):
            parser.error("Training config must be a JSON object")
        actions = {action.dest: action for action in parser._actions}
        for key, value in values.items():
            if key not in actions or key in {"help", "config"}:
                parser.error(f"Unknown config key: {key}")
            action = actions[key]
            if action.nargs == 0:
                if not isinstance(value, bool):
                    parser.error(f"{key} must be true or false")
                if value:
                    defaults.append(action.option_strings[0])
            elif value is not None:
                defaults.extend([action.option_strings[0], str(value)])
    return parser.parse_args(defaults + argv)
