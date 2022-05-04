import bpy
import sys
import shutil
import zipfile
from pathlib import Path
from bpy.props import (FloatProperty,
                        BoolProperty,
                        EnumProperty,
                        StringProperty,
                        IntProperty,
                        PointerProperty,
                        FloatVectorProperty)

def get_addon_prefs():
    '''
    function to read current addon preferences properties
    access with : get_addon_prefs().super_special_option
    '''
    import os 
    addon_name = os.path.splitext(__name__)[0]
    preferences = bpy.context.preferences
    addon_prefs = preferences.addons[addon_name].preferences
    return (addon_prefs)

def open_addon_prefs():
    '''Open addon prefs windows with focus on current addon'''
    from .__init__ import bl_info
    wm = bpy.context.window_manager
    wm.addon_filter = 'All'
    if not 'COMMUNITY' in  wm.addon_support: # reactivate community
        wm.addon_support = set([i for i in wm.addon_support] + ['COMMUNITY'])
    wm.addon_search = bl_info['name']
    bpy.context.preferences.active_section = 'ADDONS'
    bpy.ops.preferences.addon_expand(module=__package__)
    bpy.ops.screen.userpref_show('INVOKE_DEFAULT')

class SWD_OT_open_addon_prefs(bpy.types.Operator):
    bl_idname = "swd.open_addon_prefs"
    bl_label = "Open Addon Prefs"
    bl_description = "Open user preferences window in addon tab and prefill the search with addon name"
    bl_options = {"REGISTER"}

    def execute(self, context):
        open_addon_prefs()
        return {'FINISHED'}

class SWD_OT_check_ffmpeg(bpy.types.Operator):
    """check if ffmpeg is in path"""
    bl_idname = "swd.check_ffmpeg"
    bl_label = "Check ffmpeg in system path"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    def invoke(self, context, event):
        # check path command
        import  shutil
        self.sys_path_ok = shutil.which('ffmpeg')
        
        # check windows exe
        self.local_ffmpeg = False
        self.is_window_os = sys.platform.startswith('win')
        if self.is_window_os:
            ffbin = Path(__file__).parent / 'ffmpeg.exe'
            self.local_ffmpeg = ffbin.exists()

        return context.window_manager.invoke_props_dialog(self, width=250)
    
    def draw(self, context):
        layout = self.layout

        if self.local_ffmpeg:
            layout.label(text='ffmpeg.exe found in addon folder (this binary will be used)', icon='CHECKMARK')
        
        if self.sys_path_ok:
            layout.label(text='ffmpeg is in system PATH', icon='CHECKMARK')
        else:
            layout.label(text='ffmeg is not in system PATH', icon='X') # CANCEL

    def execute(self, context):
        return {'FINISHED'}

## download ffmpeg

def dl_url(url, dest):
    '''download passed url to dest file (include filename)'''
    import urllib.request
    import time
    start_time = time.time()
    with urllib.request.urlopen(url) as response, open(dest, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
    print(f"Download time {time.time() - start_time:.2f}s",)

def unzip(zip_path, extract_dir_path):
    '''Get a zip path and a directory path to extract to'''
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir_path)

class SWD_OT_download_ffmpeg(bpy.types.Operator):
    """Download if ffmpeg is in path"""
    bl_idname = "swd.download_ffmpeg"
    bl_label = "Download ffmpeg"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    def invoke(self, context, event):
        # Check if an ffmpeg version is already in addon path
        addon_loc = Path(__file__).parent
        self.ff_zip = addon_loc / 'ffmpeg.zip'
        self.ffbin = addon_loc / 'ffmpeg.exe'
        self.exists = self.ffbin.exists()
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def draw(self, context):
        layout = self.layout
        # layout.label(text='This action will download an ffmpeg release from ffmpeg repository')
        col = layout.column()
        if self.exists:
            col.label(text='ffmpeg is already in addon folder, delete and re-download ? (~90 Mo)', icon='INFO')
        else:
            col.label(text='This will download ffmpeg release from ffmpeg github page in addon folder (~90 Mo)', icon='INFO')
            col.label(text='Would you like to continue ?')

    def execute(self, context):
        if self.exists:
            self.ffbin.unlink()
        
        ## hardcoded compatible release
        release_url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2021-11-23-12-19/ffmpeg-n4.4.1-2-gcc33e73618-win64-gpl-4.4.zip' 
        dl_url(release_url, str(self.ff_zip))

        with zipfile.ZipFile(str(self.ff_zip), 'r') as zip_ref:
            zip_ffbin = None
            for f in zip_ref.infolist():
                if Path(f.filename).name == 'ffmpeg.exe':
                    zip_ffbin = f
                    break
    
            if zip_ffbin:
                zip_ffbin.filename = Path(zip_ffbin.filename).name
                zip_ref.extract(zip_ffbin, path=str(self.ffbin.parent)) # extract(self, member, path=None, pwd=None)

        if not zip_ffbin:
            self.report({'ERROR'}, 'ffmpeg not found in downloaded zip')
        
        if self.ff_zip.exists():
            self.ff_zip.unlink()
        
        if self.ffbin.exists():
            prefs = get_addon_prefs()
            prefs.path_to_ffmpeg = str(self.ffbin.resolve())

        self.report({'INFO'}, f'Installed: {self.ffbin.resolve()}')
        return {'FINISHED'}


class SWD_sound_waveform_display_addonpref(bpy.types.AddonPreferences):
    bl_idname = __name__.split('.')[0]

    path_to_ffmpeg : StringProperty(
        name="Path to ffmpeg binary",
        description='Set the path to ffmpeg or leave empty if ffmpeg is in your path',
        subtype='FILE_PATH')

    force_mixdown : BoolProperty(
        name="Force Audio Mixdown",
        default=True,
        description='Use mixdown even for displaying single audio track \
            \nSlightly longer calculation but generally more accurate waveform')

    wave_color: FloatVectorProperty(
        name="Waveform Color",
        subtype='COLOR_GAMMA', # 'COLOR'
        size=3,
        default=(0.2392, 0.5098, 0.6941),
        min=0.0, max=1.0,
        description="Color of the waveform")

    wave_detail : EnumProperty(
        name="Waveform details", description="Precision (by increasing resolution) of the sound waveform", 
        default='4096x1024', options={'HIDDEN', 'SKIP_SAVE'},
        items=(
            # ('400x100', 'Blocky', 'Resolution of the generated wave image', 0),
            ('512x128', 'Blocky', 'Resolution of the generated wave image', 0),
            ('1024x256', 'Very Low', 'Resolution of the generated wave image', 1),
            ('2048x512', 'Low', 'Resolution of the generated wave image', 2),
            ('4096x1024', 'Medium', 'Resolution of the generated wave image', 3),
            ('8192x2048', 'High', 'Resolution of the generated wave image', 4),
            # ('12000x3000', 'Very High', 'Resolution of the generated wave image', 5), # too high
            # ('16384x4096', 'Super High', 'Resolution of the generated wave image', 6), # too high
            ))

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        # layout.use_property_decorate = False

        box = layout.box()
        box.label(text='Waveform Options:')
        box.prop(self, "wave_color")
        box.prop(self, "wave_detail")
        box.prop(self, "force_mixdown")

        box = layout.box()
        box.label(text='FFmpeg check and installation:')
        col = box.column()
        # col.label(text="This addon use ffmpeg to generate the waveform (need a recent version)")
        
        row = col.row()
        row.label(text="This functionallity need a recent ffmpeg binary")

        row.operator('wm.url_open', text='FFmpeg Download Page', icon='URL').url = 'https://www.ffmpeg.org/download.html'
        if sys.platform.startswith('win'):
            col.operator('swd.download_ffmpeg', text='Auto-install FFmpeg (windows)', icon='IMPORT')

        row = col.row()
        row.operator('swd.check_ffmpeg', text='Check if ffmpeg in PATH', icon='PLUGIN')
        row = col.row()
        row.label(text="Leave field empty if ffmpeg is in system PATH")
        
        # col.label(text="May not work if space are in path.")
        box.prop(self, "path_to_ffmpeg")
        


### --- REGISTER ---

classes=(
SWD_OT_open_addon_prefs,
SWD_OT_check_ffmpeg,
SWD_OT_download_ffmpeg,
SWD_sound_waveform_display_addonpref,
)

def register(): 
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)