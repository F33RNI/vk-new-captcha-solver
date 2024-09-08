"""
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer tuo <https://unlicense.org>
"""

import argparse
import logging
import os

import cv2
import numpy as np

from _version import __version__
from extract_characters import PARAMS_DEFAULT, extract_characters
from flask_server import SERVER_IP_PORT_DEFAULT, FlaskServer
from generate_dataset import generate_dataset
from model import INPUT_HEIGHT, INPUT_WIDTH, SAVE_DIR_DEFAULT, Model

LOGGING_FORMATTER = "[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s"

EXAMPLE_USAGE = """examples:
  vk-new-captcha-solver --train "./dataset/*.png" --save "./model"
  vk-new-captcha-solver --load "./model" --save-results "./solved" --from-file "/path/to/test.png"
  vk-new-captcha-solver --load "./model" --save-results "./solved" --server "localhost:5000"
  or simply:
  vk-new-captcha-solver -l -o "./solved" -i "localhost:5000"
  vk-new-captcha-solver -l -i
"""

DATASET_FILES_PATTERN_DEFAULT = os.path.join("dataset", "*.png")


def parse_args() -> argparse.Namespace:
    """Parses cli arguments

    Returns:
        argparse.Namespace: parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="New (russian) VK captcha solver with built-in server",
        epilog=EXAMPLE_USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    load_train_group = parser.add_mutually_exclusive_group(required=True)
    load_train_group.add_argument(
        "-t",
        "--train",
        nargs="?",
        const="",
        type=str,
        required=False,
        help=f"train model with provided files (Default: {DATASET_FILES_PATTERN_DEFAULT})."
        " Each file must have captcha's value name (Example: жхфш.png)",
        metavar="DATASET_FILES_PATTERN",
    )
    load_train_group.add_argument(
        "-l",
        "--load",
        nargs="?",
        const="",
        type=str,
        required=False,
        help=f"load model and labels map from directory (Default: {SAVE_DIR_DEFAULT})",
        metavar="MODEL_DIR",
    )
    parser.add_argument(
        "-s",
        "--save",
        nargs="?",
        const="",
        type=str,
        required=False,
        help=f"save model and labels map (after training or loading it) into directory (Default: {SAVE_DIR_DEFAULT})",
        metavar="MODEL_DIR",
    )
    parser.add_argument(
        "-f",
        "--from-file",
        default=None,
        type=str,
        required=False,
        help='solve captcha from image file (Example: --from-file="captcha.png")',
        metavar="IMAGE_FILE_PATH",
    )
    parser.add_argument(
        "-i",
        "--server",
        nargs="?",
        const="",
        type=str,
        required=False,
        help=f'start server on IP:Port (Default: {SAVE_DIR_DEFAULT}) (Example: --server="0.0.0.0:8090")'
        " Send POST request with image as base64 (text/plain) to solve it. Response will also be in text/plain format",
        metavar="SERVER_IP_PORT",
    )
    parser.add_argument(
        "-o",
        "--save-results",
        default=None,
        type=str,
        required=False,
        help="save solved captchas as images with result as name into directory",
        metavar="RESULTS_DIR",
    )

    params_help = []
    for key, value in PARAMS_DEFAULT.items():
        params_help.append(f"{key} (Default: {value})")
    parser.add_argument(
        "-p",
        "--params",
        metavar="KEY=VALUE",
        nargs="+",
        required=False,
        help="parameters for segmentation and training as key=value pairs"
        " (Ex.: -e training_epochs=50)"
        " NOTE: All values are always treated as integers"
        " Available keys: training_epochs (Default: 20), " + ", ".join(params_help),
    )

    parser.add_argument("-d", "--debug", action="store_true", default=False, help="show debug images of segmentation")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
        help="show program's version number and exit",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point"""
    # Parse cli arguments
    args = parse_args()

    # Initialize logging
    logging.basicConfig(level=logging.INFO, format=LOGGING_FORMATTER)

    # Parse params
    params: dict[str, int] = {}
    if args.params:
        for param in args.params:
            key, value = param.split("=")
            params[key.strip()] = int(value.strip())
    logging.info(f"Provided segmentation/training parameters: {params}")

    # Load model
    model_ = None
    if args.load is not None:
        if not args.load:
            args.load = SAVE_DIR_DEFAULT
        logging.info(f"--load argument provided. Directory: {args.load}")
        model_ = Model(args.load)

    # Train model
    if args.train is not None:
        if not args.train:
            args.train = DATASET_FILES_PATTERN_DEFAULT
        logging.info(f"--train argument provided. Pattern: {args.train}")
        if args.save is None:
            logging.warning("No --save argument provided! Model will not be saved")

        images, label_idx, labels_map, unique_labels = generate_dataset(args.train, debug=args.debug, params=params)
        model_ = Model(labels=unique_labels)
        model_.set_labels_map(labels_map)
        model_.train(images, label_idx, epochs=params.get("training_epochs", 20))

        if args.save is None:
            logging.warning("No --save argument provided! Model will not be saved")

    # Save model
    if args.save is not None:
        if not args.save:
            args.save = SAVE_DIR_DEFAULT
        logging.info(f"--save argument provided. Directory: {args.save}")
        model_.save(args.save)

    # Create output directory if needed
    if args.save_results:
        if not os.path.exists(args.save_results):
            logging.info(f"Creating {args.save_results} directory")
            os.makedirs(args.save_results)
        logging.info(f"Directory for saving results: {args.save_results}")
    else:
        logging.info("No directory for saving solved captchas provided (if you want you can add -o argument)")

    # Solve from file
    if args.from_file:
        logging.info(f"Solving from {args.from_file}")
        stream = open(args.from_file, "rb")
        image = cv2.imdecode(np.frombuffer(stream.read(), dtype=np.uint8), cv2.IMREAD_COLOR)
        stream.close()

        segments = extract_characters(
            image, output_width=INPUT_WIDTH, output_height=INPUT_HEIGHT, debug=args.debug, params=params
        )
        output = "".join(model_.predict(segments))
        logging.info(f"Solved: {output}")
        if args.save_results:
            logging.info(f'Saving as {os.path.join(args.save_results, f"{output}.png")}')
            with open(os.path.join(args.save_results, f"{output}.png"), "wb+") as file_io:
                file_io.write(cv2.imencode(".png", image)[1].tobytes())

    # Start server
    if args.server is not None:
        if not args.server:
            args.server = SERVER_IP_PORT_DEFAULT
        ip, port = args.server.split(":")
        port = int(port.strip())
        FlaskServer(model_, args.save_results, args.debug, params).run(ip, port)

    logging.info("Nothing more to do. Exiting")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
