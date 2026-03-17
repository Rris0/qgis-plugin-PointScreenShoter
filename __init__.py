# -*- coding: utf-8 -*-

def classFactory(iface):
    from .pointscreenshoter import PointScreenShoterPlugin
    return PointScreenShoterPlugin(iface)
