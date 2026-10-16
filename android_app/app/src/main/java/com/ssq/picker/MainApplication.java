package com.ssq.picker;

import android.app.Application;
import android.util.Log;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class MainApplication extends Application {

    @Override
    public void onCreate() {
        super.onCreate();
        try {
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(this));
            }
        } catch (Throwable e) {
            Log.e("SSQ", "python start failed", e);
        }
    }
}
