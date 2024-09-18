A script I made to convert TextSequences to .ass (SubStation Alpha) subtitle format.


![alt text](github/sequence.png)
![alt text](github/file.png)

Check out the [test blend file](test-files/) for an example. It shows off many of the features in the script, featuring Tom Cardy's "Paint That Lady" because I thought it was funny. Audio is not provided.

Many features are missing at the time. For the best experience, try to install an "Arial"-esque font and refrain from updating fields in the Layout dropdown menu.

![alt text](github/layout.png)

### Installation:

To install the subs dependency, run 
```bash
/path/to/blender/4.3/python/python -m pip install pysubs2
```
The script will not work without this package.


Select the text sequences in your VSE and run the 
script in a window.
To change the filename of the resulting .ass, edit the OUTPUT_PATH variable in the main.py variable.

I may turn this into an extension in the future, Idk
