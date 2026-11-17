package com.demo.a11ycount;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** 供 adb 触发一次重新计数：am broadcast -a com.demo.a11ycount.COUNT */
public class CountReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        CountService s = CountService.INSTANCE;
        if (s != null) s.count("manual");
    }
}