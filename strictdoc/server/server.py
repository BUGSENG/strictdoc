import os

import uvicorn

from strictdoc import STRICTDOC_ROOT_PATH
from strictdoc.cli.cli_arg_parser import ServerCommandConfig
from strictdoc.server.config import SDocServerEnvVariable


def run_strictdoc_server(*, config: ServerCommandConfig):
    # uvicorn.run does not support passing arguments to the main
    # function (strictdoc_production_app). Passing the config through the
    # environmental variables interface.
    os.environ[SDocServerEnvVariable.INPUT_PATH] = config.input_path
    os.environ[SDocServerEnvVariable.OUTPUT_PATH] = config.output_path
    os.environ[SDocServerEnvVariable.RELOAD] = str(config.reload)

    uvicorn.run(
        "strictdoc.server.app:strictdoc_production_app",
        app_dir=".",
        # debug=False,
        factory=True,
        host="127.0.0.1",
        log_level="info",
        port=8001,
        reload=config.reload,
        reload_dirs=[
            STRICTDOC_ROOT_PATH,
            config.input_path,
        ],
        # reload_delay: Optional[float] = None,
        reload_includes=[
            "*.py",
            "*.sdoc",
            "*.html",
            "*.css",
        ],
        # reload_excludes=[
        #     "**/developer/sandbox/output/**/*",
        #     # "*output*",
        # ],
        # root_path: str = "",
    )
