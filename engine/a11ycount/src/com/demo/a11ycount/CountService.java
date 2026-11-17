package com.demo.a11ycount;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.io.File;
import java.io.FileWriter;

/**
 * 只读计数服务（demo 用）：把"实时无障碍树"的节点数写成一个 json 文件。
 *
 * 目的：验证 ADR-01 的门槛——`uiautomator dump` 与实时树到底差多少。
 * 不做任何点击/输入/手势，只遍历节点。
 */
public class CountService extends AccessibilityService {
    static volatile CountService INSTANCE;

    @Override
    protected void onServiceConnected() {
        INSTANCE = this;
        write(-1, -1, "connected");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent e) {
        if (e == null) return;
        int type = e.getEventType();
        if (type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                || type == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) {
            count("event");
        }
    }

    @Override
    public void onInterrupt() { }

    void count(String reason) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            write(-1, -1, "no-root:" + reason);
            return;
        }
        int[] acc = new int[]{0, 0};
        walk(root, acc);
        String pkg = root.getPackageName() == null ? "" : root.getPackageName().toString();
        write(acc[0], acc[1], pkg + ":" + reason);
    }

    private void walk(AccessibilityNodeInfo n, int[] acc) {
        if (n == null) return;
        acc[0]++;
        boolean interactive = n.isClickable() || n.isLongClickable() || n.isCheckable()
                || n.isScrollable() || n.isEditable();
        if (interactive) acc[1]++;
        int c = n.getChildCount();
        for (int i = 0; i < c; i++) {
            AccessibilityNodeInfo ch = n.getChild(i);
            if (ch == null) continue;
            walk(ch, acc);
            ch.recycle();
        }
    }

    private void write(int nodes, int interactive, String tag) {
        try {
            File dir = getExternalFilesDir(null);
            if (dir == null) return;
            if (!dir.exists()) dir.mkdirs();
            File f = new File(dir, "count.json");
            FileWriter w = new FileWriter(f, false);
            w.write("{\"nodes\":" + nodes + ",\"interactive\":" + interactive
                    + ",\"tag\":\"" + tag.replace("\"", "") + "\",\"ts\":" + System.currentTimeMillis() + "}");
            w.close();
        } catch (Throwable ignored) { }
    }
}