# Voxel Gen Tools for 3D Visualization in Blender

Blender 4.3+ add-on to convert 3D image stacks into models. Converts binary arrays into colormapped structures representing quantitative parameters or datasets. Built to analyze variations and patterns for segmented imaging data.

### Citation 

Chang K, Deshmukh A, Verma R, Loconte V, White KL. Classifying Biophysical Subpopulations of Insulin Secretory Granules using Quantitative Whole Cell Structure Analysis. bioRxiv [Preprint]. 2025 Sep 15:2025.09.09.675239. doi: 10.1101/2025.09.09.675239. PMID: 41000628; PMCID: PMC12458229.

### Overview

This Blender add-on is a plus for 3D microscopy visualization, and suits a wide variety of imaging modalities (previously tested with FIB-SEM, Cryo-ET, and SXT)! Convert your segmentation masks and parametrized data into colorful 3D models that provide both *qualitative* and *quantitative* visual patterns.  

*Key Features*
- Complete pipeline from voxel generation to smoothing and subdivision.
- Built-in material generator optimized to utilize scientific colormaps.
- Base code for data preparation and file conversion.
No prior Blender experience is required, and YouTube and StackExchange are ever-present helpers.

---

# Example Renders

The images below highlight key renders generated with the various tools provided in this add-on package.

## Soft X-Ray Tomography (SXT)

## Focused Ion Beam Scanning Electron Microscopy (FIB-SEM)
This data was obtained from [BetaSeg](https://betaseg.github.io/). 

## Cryo Electron Tomography (Cryo-ET)

---

# Installation and Usage

This information is also available in document and video form under [tutorials_documentation](pictures_screenshots).

## Step 0: Installation of the Voxel Tools Add-on

> Download the .zip package from this repository. Extract the contents and locate the add-on file in **voxel-gen-tools-for-blender > add_on_code > add_on_voxel_tools.py**.

> Download Blender’s latest version from their website and follow the package installation steps. Open a new General file. The previous contents can be deleted through **A > Delete**.

<p align="middle"> <img src="pictures_screenshots/0.1.png" height="300"/> <img src="pictures_screenshots/0.2.png" height="300"/> </p>  

Go to **Edit > Preferences > Add-ons** and locate the top right button: Add-ons Settings. Click and select Refresh Local, then Install from Disk… Select the .py file found earlier in the extracted .zip. The add-on will pop up and be pre-selected in the list.

<p align="middle"> <img src="pictures_screenshots/0.3.png" width="500"/> </p>  
<p align="middle"> <img src="pictures_screenshots/0.4.png" width="500"/> </p>  

On the blank screen, click **N** to open the Sidebar. The Voxel Gen Tools tab will appear last. 

<p align="middle"> <img src="pictures_screenshots/0.5.png" width="500"/> </p>  

## Step 1: Environment Setup

Before a mesh may be generated, the environment’s unit system must be set up. With the Sidebar open (N), select the tab **View > Clip Start > End**, then add 000 to the end to set it to **1000000 m**. This is due to the large mesh size.

<p align="middle"> <img src="pictures_screenshots/1.5.png" width="500"/> </p>  

Add a camera to the scene by clicking **Shift + A > Camera**. The actual focus can be adjusted later. On the right side of the screen, click on the green camera icon, and adjusted clip end to the same value as the environment (1000000). 

<p align="middle"> <img src="pictures_screenshots/1.4.png" height="300"/> <img src="pictures_screenshots/1.6.png" height="300"/> </p>  

Add basic lighting to the scene through **Shift + A > Light > Sun**. Again, on the right side of the screen, click the green light bulb symbol, then change Strength to **5** and Angle to **180 deg**. These values can be manipulated for more control and effect. 

<p align="middle"> <img src="pictures_screenshots/1.7.png" height="300"/> <img src="pictures_screenshots/1.8.png" height="300"/> </p>  

Finally, for basic render settings, go to the Render properties tab. To start, for simplicity, use the **EEVEE Engine**. Under the **Film** tab, toggle **Transparent** to create a background-less render. This allows for control over the effect of backdrop lightning and color.

<p align="middle"> <img src="pictures_screenshots/1.9.png" height="300"/> </p>  

The next tab allows you to adjust the frame size. Personal preferences are a square screen size of 5120x5120. 

<p align="middle"> <img src="pictures_screenshots/1.10.png" height="300"/> </p>  

> Blender videos and forums can provide basic starting points for lighting, materials, and camera adjustments to suit the rendering needs.

