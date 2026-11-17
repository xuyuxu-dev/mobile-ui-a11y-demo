package com.demo.canvas;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.View;

/**
 * 可交互的 Canvas 夹具（demo 专用，包名 com.demo.canvas，与生产应用无关）。
 *
 * 与 QUIZ 的 MockExerciseActivity 的区别：**这个会处理触摸**。
 * 目的：让"视觉定位 → 点击 → 状态转移 → 视觉验证"这条链路可以完整验证，
 * 而不必依赖任何真实课堂/学习平台。
 *
 * 页面没有任何 TextView，无障碍树里只有 1 个 CustomView。
 */
public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(new Pad(this));
    }

    static class Pad extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint txt = new Paint(Paint.ANTI_ALIAS_FLAG);
        private int selected = 3;          // 默认选中 D
        private final String[] labels = {"A", "B", "C", "D"};
        private final RectF[] rects = new RectF[4];

        Pad(android.content.Context c) {
            super(c);
            txt.setColor(Color.WHITE);
            txt.setTextAlign(Paint.Align.CENTER);
            txt.setFakeBoldText(true);
        }

        private void layout() {
            int w = getWidth(), h = getHeight();
            int size = (int) (w * 0.19f);
            int gap = (w - size * 4) / 5;
            int top = (int) (h * 0.86f) - size / 2;
            for (int i = 0; i < 4; i++) {
                int left = gap + i * (size + gap);
                rects[i] = new RectF(left, top, left + size, top + size);
            }
        }

        @Override
        protected void onDraw(Canvas c) {
            super.onDraw(c);
            if (rects[0] == null) layout();
            c.drawColor(Color.WHITE);
            p.setColor(Color.parseColor("#333333"));
            txt.setColor(Color.parseColor("#333333"));   // 标题颜色：首帧是白字白底，会看不见
            txt.setTextSize(getWidth() * 0.055f);
            c.drawText("Canvas fixture (no TextView)", getWidth() / 2f, getHeight() * 0.12f, txt);
            txt.setTextSize(getWidth() * 0.04f);
            c.drawText("tap any letter - selection moves", getWidth() / 2f, getHeight() * 0.18f, txt);
            for (int i = 0; i < 4; i++) {
                boolean on = (i == selected);
                p.setColor(on ? Color.parseColor("#3B82F6") : Color.parseColor("#EEEEEE"));
                c.drawOval(rects[i], p);
                txt.setColor(on ? Color.WHITE : Color.parseColor("#111111"));
                txt.setTextSize(rects[i].width() * 0.58f);
                c.drawText(labels[i], rects[i].centerX(),
                        rects[i].centerY() + rects[i].height() * 0.16f, txt);
            }
        }

        @Override
        public boolean onTouchEvent(MotionEvent e) {
            if (e.getAction() == MotionEvent.ACTION_DOWN) {
                if (rects[0] == null) layout();
                for (int i = 0; i < 4; i++) {
                    if (rects[i].contains(e.getX(), e.getY())) {
                        selected = i;
                        invalidate();
                        return true;
                    }
                }
            }
            return true;
        }
    }
}