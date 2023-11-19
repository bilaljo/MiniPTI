# GUI Configuration
In order to make the GUI flexible, it can be configured with a mini-programming language called "MJSON" (short for MiniPTI JSON). The JSON file, with a fixed structure, will be compiled into a Python data class and will change the GUI respectively.
The file sandbox.json provides an example, which contains the basic structure that a valid file needs to have. If you want to use it, simply set use to true. Note that the first file which has use set to true will be the one used. Invalid files are ignored, and only the configurations in the configs folder will be scanned for files.
If you lose the file (or corrupt it), you can regenerate it by running (assuming you are in the MiniPTI folder) the following command on Linux:
```
python3 minipti/gui/model/configuration.py
```

Or on Windows:
```bash
python minipti\gui\model\configuration.py
```
This will generate a file called sandbox.json that contains only default values and the required structure.
