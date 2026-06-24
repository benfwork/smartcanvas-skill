Context:

The SmartCanvas Skill is to assist in the creation and updating of SmartCanvas Products, which are customizable

Main Functions:

1. Image Dropdown Creator

Input:
We will input:
- an export of an exisitng SmartCanvas template (ZIP)
- a zip/directory of images 

The skill should add all of the images to the SmartCanvas within one folder of images. 

This is the process that we follow to create an image select-dropdown within the UI, so the ZIP skill may have to do the same:

- create a form field selector with type Image List
- for each photo: 
    - create a layer
    - create a switch
    - connect the switch to the layer
    - add the switch/image pair to the form field select
    - edit the logic in the switch to match the image file name in the form field

The result should output a new SmartCanvas ZIP file with the images part of a dropdown select.

To come up with the script for this function, I have given you a folder called example-zip with:
1. a blank design ZIP
2. a ZIP with two images added in two different layers (in the same Test_category)
3. another zip with those two images linked to two different switches and added to the same image dropdown select.  
