package com.ssq.picker;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.AssetManager;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

public class MainActivity extends Activity {

    private static final String TAG = "SSQ";
    private static final int REQ_OPEN_CSV = 1001;

    private Python py;
    private PyObject mod;
    private volatile boolean initialized = false;

    // 选号页（对齐桌面版：排除号勾选网格 + 横排圆形号码球）
    private TextView tvStatus, tvPoolLbl;
    private CheckBox[] redChecks = new CheckBox[33];
    private CheckBox[] blueChecks = new CheckBox[16];
    private boolean[] exclRed = new boolean[34];
    private boolean[] exclBlue = new boolean[17];
    private LinearLayout resultsBox;
    private Button btPick, btRandom;

    // 一机一码授权（v2.6）
    private static final String PREF_ACT = "ssq_activate";
    private volatile boolean activated = false;
    private String deviceCode = "";
    private LinearLayout activatePanel;
    private TextView tvActivateHint;
    private EditText etActivate;
    // 回测页
    private EditText etBtRounds, etBtWindow;
    private TextView tvBtOut;
    private Button btBacktest;

    // 数据页
    private TextView tvStats, tvHistory;
    private EditText etImport;
    private TextView tvImportHint, tvSyncHint;

    private Uri pendingCsvUri;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // ---- 一机一码授权：读取设备码，恢复本机激活状态 ----
        deviceCode = loadDeviceCode();
        SharedPreferences prefs = getSharedPreferences(PREF_ACT, MODE_PRIVATE);
        activated = prefs.getBoolean("activated", false)
                && deviceCode.equals(prefs.getString("device", ""));

        // ---- 界面骨架：自绘标签栏 + 四页内容区 ----
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);

        LinearLayout tabBar = new LinearLayout(this);
        tabBar.setOrientation(LinearLayout.HORIZONTAL);
        String[] titles = {"选号", "回测", "数据", "说明"};
        tabButtons = new Button[4];
        for (int i = 0; i < 4; i++) {
            final int idx = i;
            tabButtons[i] = new Button(this);
            tabButtons[i].setText(titles[i]);
            tabButtons[i].setAllCaps(false);
            tabButtons[i].setTextSize(15);
            tabButtons[i].setOnClickListener(v -> showTab(idx));
            tabBar.addView(tabButtons[i], new LinearLayout.LayoutParams(0,
                    LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        }
        root.addView(tabBar);

        FrameLayout content = new FrameLayout(this);
        tabViews = new View[4];
        tabViews[0] = buildPickTab();
        tabViews[1] = buildBacktestTab();
        tabViews[2] = buildDataTab();
        tabViews[3] = buildAboutTab();
        for (View v : tabViews) {
            content.addView(v, new FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT));
        }
        root.addView(content, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);

        showTab(0);

        // ---- 初始化 Python（后台线程，避免卡 UI） ----
        final String dbPath = copyDb();
        new Thread(() -> {
            try {
                if (dbPath == null) {
                    // 数据库不可用时直接给出明确失败状态，不再继续初始化
                    runOnUiThread(() -> {
                        if (tvStatus != null) {
                            tvStatus.setText("数据库初始化失败：内置数据读取异常，"
                                    + "请重新安装本应用。");
                        }
                    });
                    return;
                }
                if (!Python.isStarted()) {
                    // Application 中应已启动；此处为兜底
                    Python.start(new AndroidPlatform(getApplicationContext()));
                }
                py = Python.getInstance();
                mod = py.getModule("main");
                mod.callAttr("init", dbPath);
                initialized = true;
                String statsTxt = "";
                try {
                    statsTxt = mod.callAttr("get_stats").toString();
                } catch (Throwable ignored) { }
                final String fstats = statsTxt;
                runOnUiThread(() -> {
                    if (tvStatus != null) {
                        String s = "就绪。完全本地运行，不依赖网络。";
                        try {
                            JSONObject st = new JSONObject(fstats);
                            s = "本地数据：" + st.getInt("总期数") + " 期，最新期号 "
                                    + st.getString("最新期") + "（历史统计模式，全量建模）";
                        } catch (Exception ignored) { }
                        tvStatus.setText(s);
                    }
                    if (btPick != null) btPick.setEnabled(true);
                    if (btRandom != null) btRandom.setEnabled(true);
                    if (btBacktest != null) btBacktest.setEnabled(true);
                });
            } catch (Throwable e) {
                Log.e(TAG, "init failed", e);
                runOnUiThread(() -> {
                    if (tvStatus != null) tvStatus.setText("初始化失败：" + e);
                });
            }
        }).start();
    }

    // ================= 选号页（对齐桌面版） =================
    private View buildPickTab() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);

        tvStatus = new TextView(this);
        tvStatus.setTextSize(14);
        tvStatus.setTypeface(Typeface.DEFAULT_BOLD);
        tvStatus.setTextColor(0xFF1d6fb8);
        root.addView(tvStatus);

        // ---- 激活区（一机一码，未激活时显示） ----
        tvActivateHint = new TextView(this);
        tvActivateHint.setTextSize(13);
        tvActivateHint.setTypeface(Typeface.DEFAULT_BOLD);
        tvActivateHint.setTextColor(0xFFc0392b);
        tvActivateHint.setText("本机未激活\n设备码：" + fmtDeviceCode()
                + "\n请把设备码发给程序所有者，换取激活码后粘贴到下方");
        root.addView(tvActivateHint);

        activatePanel = new LinearLayout(this);
        activatePanel.setOrientation(LinearLayout.HORIZONTAL);
        etActivate = new EditText(this);
        etActivate.setHint("在此粘贴激活码");
        etActivate.setTextSize(13);
        etActivate.setSingleLine(true);
        activatePanel.addView(etActivate, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        Button btActivate = new Button(this);
        btActivate.setText("激活");
        btActivate.setAllCaps(false);
        btActivate.setOnClickListener(v -> doActivate());
        activatePanel.addView(btActivate, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        root.addView(activatePanel);
        applyActivateUI();

        // 排除红球网格（1-33，8 列 × 5 行；手机窄屏 11 列会挤压，改 8 列保证号码可见）
        root.addView(label("排除红球（1-33，勾选后智能选号不使用）"));
        for (int row = 0; row < 5; row++) {
            LinearLayout rl = new LinearLayout(this);
            rl.setOrientation(LinearLayout.HORIZONTAL);
            for (int col = 0; col < 8; col++) {
                int idx = row * 8 + col;
                if (idx >= 33) break;
                CheckBox cb = new CheckBox(this);
                cb.setText(String.format("%02d", idx + 1));
                cb.setTextSize(11);
                cb.setAllCaps(false);
                cb.setMinHeight(0);
                cb.setPadding(0, 0, 0, 0);
                final int num = idx + 1;
                cb.setOnCheckedChangeListener((b, on) -> exclRed[num] = on);
                redChecks[idx] = cb;
                rl.addView(cb, new LinearLayout.LayoutParams(0,
                        LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            }
            root.addView(rl);
        }

        // 排除蓝球网格（1-16，8 列 × 2 行，与桌面版一致）
        root.addView(label("排除蓝球（1-16）"));
        for (int row = 0; row < 2; row++) {
            LinearLayout rl = new LinearLayout(this);
            rl.setOrientation(LinearLayout.HORIZONTAL);
            for (int col = 0; col < 8; col++) {
                int idx = row * 8 + col;
                if (idx >= 16) break;
                CheckBox cb = new CheckBox(this);
                cb.setText(String.format("%02d", idx + 1));
                cb.setTextSize(11);
                cb.setAllCaps(false);
                cb.setMinHeight(0);
                cb.setPadding(0, 0, 0, 0);
                final int num = idx + 1;
                cb.setOnCheckedChangeListener((b, on) -> exclBlue[num] = on);
                blueChecks[idx] = cb;
                rl.addView(cb, new LinearLayout.LayoutParams(0,
                        LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            }
            root.addView(rl);
        }

        // 按钮行：智能选号（重跑引擎）+ 纯随机 5 注（与桌面版一致）
        LinearLayout btnRow = new LinearLayout(this);
        btnRow.setOrientation(LinearLayout.HORIZONTAL);
        btPick = new Button(this);
        btPick.setText("智能选号（重跑引擎）");
        btPick.setEnabled(initialized);
        btnRow.addView(btPick, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        btRandom = new Button(this);
        btRandom.setText("纯随机 5 注");
        btRandom.setEnabled(initialized);
        btnRow.addView(btRandom, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        root.addView(btnRow);
        // 结果区：横排圆形号码球（6 组）
        root.addView(label("智能选号结果（6 组）"));
        resultsBox = new LinearLayout(this);
        resultsBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(resultsBox);

        tvPoolLbl = new TextView(this);
        tvPoolLbl.setTextSize(12);
        tvPoolLbl.setTextColor(0xFF555555);
        root.addView(tvPoolLbl);

        btPick.setOnClickListener(v -> {
            if (!activated) { toast("本机未激活，请联系程序所有者获取激活码"); return; }
            if (!initialized) { tvStatus.setText("初始化中，请稍候…"); return; }
            btPick.setEnabled(false);
            new Thread(() -> {
                try {
                    final String s = mod.callAttr("pick",
                            excludedRed(), excludedBlue()).toString();
                    runOnUiThread(() -> {
                        renderResults(s);
                        btPick.setEnabled(true);
                    });
                } catch (Throwable e) {
                    Log.e(TAG, "pick failed", e);
                    runOnUiThread(() -> { tvPoolLbl.setText("选号失败：" + e); btPick.setEnabled(true); });
                }
            }).start();
        });

        btRandom.setOnClickListener(v -> {
            if (!activated) { toast("本机未激活，请联系程序所有者获取激活码"); return; }
            if (!initialized) { tvStatus.setText("初始化中，请稍候…"); return; }
            pickRandom5();
        });

        return scroll(root);
    }

    // ================= 一机一码授权（v2.6） =================

    /**
     * 读取稳定的本机设备码。
     * 优先使用 ANDROID_ID；若为空或异常值（全 0 / 全 F），
     * 回退为"系统硬件指纹 + 首次启动生成的持久化随机串"的摘要，
     * 避免出现空设备码导致"万能激活码"。
     */
    private String loadDeviceCode() {
        String aid = Settings.Secure.getString(getContentResolver(),
                Settings.Secure.ANDROID_ID);
        String base = (aid == null ? "" : aid.trim().toUpperCase());
        if (base.isEmpty() || base.matches("0+") || base.matches("F+")) {
            SharedPreferences p = getSharedPreferences(PREF_ACT, MODE_PRIVATE);
            String uuid = p.getString("dev_uuid", null);
            if (uuid == null) {
                uuid = java.util.UUID.randomUUID().toString();
                p.edit().putString("dev_uuid", uuid).apply();
            }
            String fp = Build.BOARD + "|" + Build.BRAND + "|" + Build.DEVICE + "|"
                    + Build.HARDWARE + "|" + Build.MODEL + "|" + Build.PRODUCT
                    + "|" + uuid;
            try {
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                byte[] h = md.digest(fp.getBytes(StandardCharsets.UTF_8));
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 8; i++) {
                    sb.append(String.format("%02X", h[i] & 0xFF));
                }
                base = sb.toString();
            } catch (Exception e) {
                base = uuid.replace("-", "").substring(0, 16).toUpperCase();
            }
        }
        return base;
    }

    /** 设备码显示格式：SSQ-XXXX-XXXX-XXXX-XXXX */
    private String fmtDeviceCode() {
        StringBuilder sb = new StringBuilder("SSQ-");
        String d = deviceCode;
        for (int i = 0; i < d.length(); i += 4) {
            if (i > 0) sb.append("-");
            sb.append(d.substring(i, Math.min(i + 4, d.length())));
        }
        return sb.toString();
    }

    /** 激活区显示/隐藏（未激活显示，已激活隐藏）。 */
    private void applyActivateUI() {
        if (activatePanel == null) return;
        if (activated) {
            activatePanel.setVisibility(View.GONE);
            tvActivateHint.setVisibility(View.GONE);
        } else {
            activatePanel.setVisibility(View.VISIBLE);
            tvActivateHint.setVisibility(View.VISIBLE);
        }
    }

    /** 点击激活：校验激活码，成功则本地记录并解锁。 */
    private void doActivate() {
        if (activated) { toast("本机已激活，无需重复激活"); return; }
        final String code = etActivate.getText().toString().trim();
        if (code.isEmpty()) { toast("请先粘贴激活码"); return; }
        if (mod == null) { toast("初始化中，请稍候再试"); return; }
        final String dev = deviceCode;
        new Thread(() -> {
            boolean ok;
            try {
                PyObject r = mod.callAttr("verify_activate", dev, code);
                ok = r != null && r.toBoolean();
            } catch (Throwable e) {
                Log.e(TAG, "verify failed", e);
                ok = false;
            }
            final boolean ok2 = ok;
            runOnUiThread(() -> {
                if (ok2) {
                    getSharedPreferences(PREF_ACT, MODE_PRIVATE).edit()
                            .putBoolean("activated", true)
                            .putString("device", deviceCode)
                            .apply();
                    activated = true;
                    applyActivateUI();
                    toast("激活成功，本机已永久解锁");
                } else {
                    toast("激活码无效，请核对后重试");
                }
            });
        }).start();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }

    /** 勾选的排除红球 → "1,5,12" 形式。 */
    private String excludedRed() {
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 33; i++) {
            if (exclRed[i]) { if (sb.length() > 0) sb.append(","); sb.append(i); }
        }
        return sb.toString();
    }

    private String excludedBlue() {
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= 16; i++) {
            if (exclBlue[i]) { if (sb.length() > 0) sb.append(","); sb.append(i); }
        }
        return sb.toString();
    }

    /** 渲染选号结果：大底行 + 六组横排号码球。 */
    private void renderResults(String json) {
        resultsBox.removeAllViews();
        try {
            JSONObject o = new JSONObject(json);
            JSONArray pool = o.getJSONArray("大底");
            JSONArray blueCands = o.getJSONArray("蓝球候选");
            List<Integer> poolList = new ArrayList<>();
            for (int i = 0; i < pool.length(); i++) poolList.add(pool.getInt(i));
            Collections.sort(poolList);
            StringBuilder sb = new StringBuilder("红球大底（投票层前18）：");
            for (int x : poolList) sb.append(String.format("%02d ", x));
            StringBuilder bc = new StringBuilder("[");
            for (int i = 0; i < blueCands.length(); i++) {
                if (i > 0) bc.append(",");
                bc.append(String.format("%02d", blueCands.getInt(i)));
            }
            bc.append("]");
            sb.append(" | 蓝球候选：").append(bc);
            tvPoolLbl.setText(sb);

            JSONObject groups = o.getJSONObject("组");
            for (int k = 1; k <= 6; k++) {
                JSONObject g = groups.getJSONObject("结果" + k);
                JSONArray reds = g.getJSONArray("红球");
                Object blue = g.get("蓝球");
                String src = g.getString("来源");
                resultsBox.addView(buildResultRow("结果" + k, reds, blue, src));
            }
        } catch (Exception e) {
            Log.e(TAG, "render failed", e);
            tvPoolLbl.setText("结果解析失败：" + e);
        }
    }

    /** 一组结果：标题固定 + 号码区可横向滑动（集合型 10 红 + 3 蓝不会截断）。 */
    private View buildResultRow(String title, JSONArray reds, Object blue, String src)
            throws org.json.JSONException {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.VERTICAL);
        row.setPadding(0, 8, 0, 8);

        // 行 1：标题（固定）+ 红球（可横滑）
        LinearLayout l1 = new LinearLayout(this);
        l1.setOrientation(LinearLayout.HORIZONTAL);
        l1.setGravity(Gravity.CENTER_VERTICAL);
        TextView t = new TextView(this);
        t.setText(title);
        t.setTextSize(13);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(0xFF333333);
        t.setWidth(dp2px(56));
        l1.addView(t);
        HorizontalScrollView hs1 = new HorizontalScrollView(this);
        hs1.setHorizontalScrollBarEnabled(false);
        LinearLayout balls1 = new LinearLayout(this);
        balls1.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < reds.length(); i++) {
            balls1.addView(ball(reds.getInt(i), true));
        }
        hs1.addView(balls1);
        l1.addView(hs1, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        row.addView(l1);

        // 行 2：蓝球（可横滑）+ 来源
        LinearLayout l2 = new LinearLayout(this);
        l2.setOrientation(LinearLayout.HORIZONTAL);
        l2.setGravity(Gravity.CENTER_VERTICAL);
        HorizontalScrollView hs2 = new HorizontalScrollView(this);
        hs2.setHorizontalScrollBarEnabled(false);
        LinearLayout balls2 = new LinearLayout(this);
        balls2.setOrientation(LinearLayout.HORIZONTAL);
        if (blue instanceof JSONArray) {
            JSONArray ba = (JSONArray) blue;
            for (int i = 0; i < ba.length(); i++) balls2.addView(ball(ba.getInt(i), false));
        } else {
            balls2.addView(ball(((Number) blue).intValue(), false));
        }
        TextView s = new TextView(this);
        s.setText(src);
        s.setTextSize(11);
        s.setTextColor(0xFF888888);
        s.setPadding(dp2px(8), 0, 0, 0);
        balls2.addView(s);
        hs2.addView(balls2);
        l2.addView(hs2, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        row.addView(l2);
        return row;
    }

    /** 圆形号码球（红底/蓝底），与桌面版 BallLabel 相同视觉。 */
    private TextView ball(int num, boolean isRed) {
        TextView tv = new TextView(this);
        tv.setText(String.format("%02d", num));
        tv.setTextColor(Color.WHITE);
        tv.setGravity(Gravity.CENTER);
        tv.setTextSize(14);
        tv.setTypeface(Typeface.DEFAULT_BOLD);
        int size = dp2px(40);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(size, size);
        lp.setMargins(dp2px(3), 0, dp2px(3), 0);
        tv.setLayoutParams(lp);
        GradientDrawable gd = new GradientDrawable();
        gd.setShape(GradientDrawable.OVAL);
        gd.setColor(isRed ? 0xFFE53935 : 0xFF1E88E5);
        tv.setBackground(gd);
        return tv;
    }

    private int dp2px(int dp) {
        return Math.round(dp * getResources().getDisplayMetrics().density);
    }

    /** 纯随机 5 注（不依赖历史数据），与桌面版一致。 */
    private void pickRandom5() {
        resultsBox.removeAllViews();
        List<Integer> poolR = new ArrayList<>();
        for (int i = 1; i <= 33; i++) if (!exclRed[i]) poolR.add(i);
        List<Integer> poolB = new ArrayList<>();
        for (int i = 1; i <= 16; i++) if (!exclBlue[i]) poolB.add(i);
        if (poolR.size() < 6 || poolB.isEmpty()) {
            tvPoolLbl.setText("排除号过多，无法生成随机注。请减少排除。");
            return;
        }
        Random rnd = new Random();
        try {
            for (int k = 1; k <= 5; k++) {
                Collections.shuffle(poolR, rnd);
                List<Integer> reds = new ArrayList<>(poolR.subList(0, 6));
                Collections.sort(reds);
                int blue = poolB.get(rnd.nextInt(poolB.size()));
                JSONArray ra = new JSONArray();
                for (int r : reds) ra.put(r);
                resultsBox.addView(buildResultRow("随机" + k, ra, blue, "纯随机（不依赖历史数据）"));
            }
        } catch (Exception e) {
            tvPoolLbl.setText("随机注生成失败：" + e);
        }
        tvPoolLbl.setText("随机 5 注（已按当前排除号过滤）");
    }

    // ================= 回测页 =================
    private View buildBacktestTab() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);

        root.addView(label("回测参数"));
        root.addView(hint("回测期数（最近 N 期，默认 500，上限 1000；手机单进程，请耐心等待）："));
        etBtRounds = input("500");
        root.addView(etBtRounds);
        root.addView(hint("回测窗口（每期用最近 W 期训练，默认 100）："));
        etBtWindow = input("100");
        root.addView(etBtWindow);

        btBacktest = new Button(this);
        btBacktest.setText("开始回测（带随机基准对照）");
        btBacktest.setEnabled(initialized);
        root.addView(btBacktest);

        tvBtOut = output();
        root.addView(tvBtOut);

        btBacktest.setOnClickListener(v -> {
            if (!activated) { toast("本机未激活，请联系程序所有者获取激活码"); return; }
            if (!initialized) { tvBtOut.setText("初始化中，请稍候…"); return; }
            btBacktest.setEnabled(false);
            tvBtOut.setText("回测中…（手机约 1-3 分钟，请保持屏幕常亮）");
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            new Thread(() -> {
                try {
                    int rounds = parseInt(etBtRounds.getText().toString(), 500, 100, 1000);
                    int window = parseInt(etBtWindow.getText().toString(), 100, 20, 500);
                    final String s = mod.callAttr("backtest_limited", rounds, window).toString();
                    runOnUiThread(() -> { tvBtOut.setText(s); btBacktest.setEnabled(true);
                        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON); });
                } catch (Throwable e) {
                    Log.e(TAG, "backtest failed", e);
                    runOnUiThread(() -> { tvBtOut.setText("回测失败：" + e); btBacktest.setEnabled(true);
                        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON); });
                }
            }).start();
        });

        root.addView(hint("\n说明：回测用历史数据逐期验证六组选号的红球命中数与蓝球命中率，"
                + "并与「随机选号基准」（红球约 1.09 个、蓝球约 6.25%）对照。"
                + "蓝球为集合候选时命中率按集合口径统计，并标注候选码数。"));

        return scroll(root);
    }

    // ================= 数据页 =================
    private View buildDataTab() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);

        root.addView(label("数据统计"));
        tvStats = output();
        root.addView(tvStats);
        Button btStats = new Button(this);
        btStats.setText("刷新统计");
        root.addView(btStats);
        btStats.setOnClickListener(v -> {
            if (!initialized) { tvStats.setText("初始化中…"); return; }
            new Thread(() -> {
                try {
                    final String s = mod.callAttr("get_stats").toString();
                    runOnUiThread(() -> tvStats.setText(s));
                } catch (Throwable e) {
                    runOnUiThread(() -> tvStats.setText("失败：" + e));
                }
            }).start();
        });

        root.addView(label("最近开奖记录"));
        tvHistory = output();
        root.addView(tvHistory);
        Button btHistory = new Button(this);
        btHistory.setText("刷新最近 20 期");
        root.addView(btHistory);
        btHistory.setOnClickListener(v -> {
            if (!initialized) { tvHistory.setText("初始化中…"); return; }
            new Thread(() -> {
                try {
                    final String s = mod.callAttr("get_history", 20).toString();
                    runOnUiThread(() -> tvHistory.setText(s));
                } catch (Throwable e) {
                    runOnUiThread(() -> tvHistory.setText("失败：" + e));
                }
            }).start();
        });

        // 手动同步开奖数据（点击后自动从福彩官网拉取最新开奖并写入本地库）
        root.addView(label("同步开奖数据"));
        root.addView(hint("点击按钮后自动连接中国福利彩票官网公开接口，"
                + "拉取最新开奖并写入本地数据库（需要网络，仅拉取不上传）。"));
        Button btSync = new Button(this);
        btSync.setText("点击同步开奖数据");
        root.addView(btSync);
        tvSyncHint = hint("");
        root.addView(tvSyncHint);
        btSync.setOnClickListener(v -> syncData(btSync));

        root.addView(label("粘贴导入开奖记录"));
        root.addView(hint("格式：每行「期号 日期 红1红2红3红4红5红6 蓝」\n"
                + "例：2026113 2026-09-30 01 05 08 12 23 30 07\n"
                + "（日期可留空；已存在的期号会覆盖更新）"));
        etImport = new EditText(this);
        etImport.setLines(4);
        etImport.setTextSize(13);
        etImport.setTypeface(Typeface.MONOSPACE);
        root.addView(etImport);
        Button btImport = new Button(this);
        btImport.setText("导入粘贴内容");
        root.addView(btImport);
        tvImportHint = hint("");
        root.addView(tvImportHint);
        btImport.setOnClickListener(v -> {
            if (!initialized) { tvImportHint.setText("初始化中…"); return; }
            final String text = etImport.getText().toString().trim();
            if (text.isEmpty()) { tvImportHint.setText("请先粘贴内容。"); return; }
            btImport.setEnabled(false);
            tvImportHint.setText("导入中…");
            new Thread(() -> {
                try {
                    final String s = mod.callAttr("import_text", text).toString();
                    runOnUiThread(() -> { tvImportHint.setText(s + "（提示：导入后数据统计/回测立即生效）"); btImport.setEnabled(true); });
                } catch (Throwable e) {
                    runOnUiThread(() -> { tvImportHint.setText("导入失败：" + e); btImport.setEnabled(true); });
                }
            }).start();
        });

        Button btCsv = new Button(this);
        btCsv.setText("从 CSV 文件导入");
        root.addView(btCsv);
        root.addView(hint("CSV 列：issue,date,red1..red6,blue（可含 week,sales,pool）"));
        btCsv.setOnClickListener(v -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            i.addCategory(Intent.CATEGORY_OPENABLE);
            i.setType("*/*");
            startActivityForResult(i, REQ_OPEN_CSV);
        });

        return scroll(root);
    }

    // ================= 说明页 =================
    private View buildAboutTab() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);

        TextView title = new TextView(this);
        title.setText("双色球历史统计工具");
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        TextView sub = new TextView(this);
        sub.setText("双色球历史数据统计参考工具");
        sub.setTextSize(13);
        sub.setGravity(Gravity.CENTER);
        sub.setTextColor(0xFF666666);
        root.addView(sub);

        TextView ver = new TextView(this);
        ver.setText("版本：V2.7（跨年修复+空码防护+隐私政策+正式签名）");
        ver.setTextSize(14);
        ver.setGravity(Gravity.CENTER);
        root.addView(ver);

        root.addView(label("激活说明（一机一码）"));
        root.addView(hint("本程序采用一机一码授权：每台手机首次打开会显示专属设备码，"
                + "需要把设备码发给程序所有者换取激活码，粘贴后永久解锁使用。\n"
                + "激活码只对生成它的那台设备有效，转发到其他手机无效；"
                + "每台设备只发放一次激活码，卸载重装后需重新联系所有者获取新码。"
                + "未激活时选号与回测不可用，仅可查看历史数据与说明。"));


        root.addView(label("应用原理"));
        root.addView(hint("本程序是一个完全本地运行的双色球历史数据统计分析工具，"
                + "不依赖网络、不上传任何数据。原理分四层："));

        root.addView(label("一、数据基础"));
        root.addView(hint("内置福彩双色球全部 3510 期历史开奖（2003001~2026113 期），"
                + "存于本地数据库。选号引擎以全量历史为样本建模，"
                + "支持手动导入或 CSV 粘贴补充新数据。"));

        root.addView(label("二、统计引擎（43 个模块）"));
        root.addView(hint("引擎对每期开奖逐号、逐区块计算 43 项统计指标（冷热频次、遗漏值、"
                + "区间分布、形态约束、蓝球双轨等），每个模块独立打分后投票汇总，"
                + "按综合评分排出红球大底（前 18 码）与蓝球候选（前 3 码）。"));

        root.addView(label("三、双轨选号机制"));
        root.addView(hint("号码轨道：按单个号码评分高低选号 → 出结果1（严格 6+1 注单）、"
                + "结果2（高分集合：10 红 + 3 蓝候选）。\n"
                + "区块轨道：按号码组合区块整体评分选号 → 出结果3（严格 6+1 注单）、"
                + "结果4（高分集合：10 红 + 3 蓝候选）。\n"
                + "横向叠加：对两轨结果做交集与补集运算 → 出结果5（注单）、结果6（集合）。\n"
                + "包含关系（结果2 包含结果1、4 包含 3、6 包含 5）由同一套评分条件自然涌现，"
                + "用于相互验证程序是否跑对，并非强行指定。"));

        root.addView(label("四、回测与随机基准"));
        root.addView(hint("回测页用历史数据逐期滚动验证六组结果，统计红球平均命中数与"
                + "蓝球命中率，并给出随机基准对照（每期红球约 1.09 个、单注蓝球 6.25%）"
                + "和奖级分布，方便评估六组选号相对随机选号的表现。"));

        root.addView(label("客观结论"));
        root.addView(hint("双色球历史统计工具不能预测开奖。双色球每期开奖为独立随机事件，"
                + "任何统计方法都无法预测下一期号码。本程序的选号与回测仅用于"
                + "观察历史数据规律、学习概率统计，请理性看待，切勿当作投注依据。"));

        root.addView(label("免责声明（非投注建议）"));
        root.addView(hint("本工具输出的所有号码、候选集合与回测数据仅供数据统计与学习参考，"
                + "不构成任何投注建议或中奖承诺，不对使用结果承担任何责任。"
                + "双色球开奖结果完全随机，不存在可预测规律。"
                + "请理性购彩，量力而行；未成年人禁止购彩。"));

        root.addView(label("隐私政策"));
        root.addView(hint("本工具完全本地运行：所有历史数据、统计结果与回测均在您设备内计算，"
                + "不收集、不存储、不上传任何个人信息，不申请电话、短信、通讯录、"
                + "位置等无关权限。唯一联网行为是数据页的「同步开奖数据」按钮，"
                + "仅在您手动点击时向福彩官网拉取公开开奖记录，"
                + "不上传本机任何数据。卸载本工具将同时清除本地全部数据。"));

        return scroll(root);
    }

    private View[] tabViews;
    private Button[] tabButtons;

    private void showTab(int idx) {
        for (int i = 0; i < 4; i++) {
            tabViews[i].setVisibility(i == idx ? View.VISIBLE : View.GONE);
            tabButtons[i].setTypeface(Typeface.DEFAULT,
                    i == idx ? Typeface.BOLD : Typeface.NORMAL);
            tabButtons[i].setTextColor(i == idx ? 0xFF1565C0 : 0xFF000000);
        }
    }

    // ================= 通用控件 =================
    private TextView label(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(15);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, 12, 0, 4);
        return t;
    }

    private TextView hint(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(12);
        t.setPadding(0, 2, 0, 6);
        return t;
    }

    private EditText input(String def) {
        EditText e = new EditText(this);
        e.setText(def);
        e.setTextSize(14);
        return e;
    }

    private TextView output() {
        TextView t = new TextView(this);
        t.setTextSize(13);
        t.setTypeface(Typeface.MONOSPACE);
        t.setPadding(0, 6, 0, 6);
        return t;
    }

    private ScrollView scroll(LinearLayout root) {
        ScrollView sv = new ScrollView(this);
        sv.addView(root);
        return sv;
    }

    private static int parseInt(String s, int def, int min, int max) {
        try {
            int v = Integer.parseInt(s.trim());
            if (v < min) v = min;
            if (v > max) v = max;
            return v;
        } catch (Exception e) {
            return def;
        }
    }

    /** 初始化数据库：优先用本地库；若内置库比本地新（新版 APK 数据升级）则重新复制覆盖。 */
    private String copyDb() {
        try {
            File out = new File(getFilesDir(), "ssq.db");
            // 内置库先解到缓存做指纹对比（assets 不可直接打开数据库）
            File assetTmp = new File(getCacheDir(), "asset_ssq.db");
            copyAssetToFile("ssq.db", assetTmp);
            long[] af = dbFingerprint(assetTmp.getAbsolutePath());
            long[] lf = (out.exists() && out.length() > 0)
                    ? dbFingerprint(out.getAbsolutePath()) : null;
            // 本地库缺失/损坏，或内置库期数更多/最新期更晚 → 用内置库覆盖
            boolean needCopy = lf == null;
            if (!needCopy && af != null && lf != null) {
                if (af[0] > lf[0] || af[1] > lf[1]) needCopy = true;
            }
            if (needCopy) {
                copyAssetToFile("ssq.db", out);
            }
            assetTmp.delete();
            return out.getAbsolutePath();
        } catch (Exception e) {
            Log.e(TAG, "copy db failed", e);
            return null;
        }
    }

    private void copyAssetToFile(String asset, File target) throws Exception {
        AssetManager am = getAssets();
        InputStream in = am.open(asset);
        FileOutputStream fos = new FileOutputStream(target);
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) fos.write(buf, 0, n);
        fos.close();
        in.close();
    }

    /** 读取库的数据指纹：[总期数, 最大期号]；读取失败返回 null。 */
    private long[] dbFingerprint(String path) {
        SQLiteDatabase db = null;
        Cursor c = null;
        try {
            db = SQLiteDatabase.openDatabase(path, null, SQLiteDatabase.OPEN_READONLY);
            c = db.rawQuery(
                    "SELECT COUNT(*), MAX(CAST(issue AS INTEGER)) FROM ssq_draws", null);
            if (c.moveToFirst()) {
                return new long[]{c.getLong(0), c.getLong(1)};
            }
            return null;
        } catch (Exception e) {
            Log.e(TAG, "db fingerprint failed: " + path, e);
            return null;
        } finally {
            if (c != null) c.close();
            if (db != null) db.close();
        }
    }

    // ================= 手动同步开奖数据（福彩官网公开接口） =================
    private void syncData(final Button btn) {
        if (!initialized) { tvSyncHint.setText("初始化中…"); return; }
        btn.setEnabled(false);
        tvSyncHint.setText("正在连接福彩官网…");
        new Thread(() -> {
            try {
                // 按缺口上限拉取（最大 500 期 ≈ 3.2 年），避免固定 20 期在长断档时静默漏数
                JSONArray list = fetchDraws(500);
                if (list == null) {
                    runOnUiThread(() -> {
                        tvSyncHint.setText("同步失败：无法连接福彩官网接口，请检查网络后重试。");
                        btn.setEnabled(true);
                    });
                    return;
                }
                // 统一字段后交给 Python 写入（已存在期号覆盖更新）
                JSONArray arr = new JSONArray();
                for (int i = 0; i < list.length(); i++) {
                    JSONObject r = list.getJSONObject(i);
                    JSONObject o = new JSONObject();
                    o.put("issue", r.optString("code"));
                    // 接口 date 形如 "2026-10-08(四)"，去掉星期后缀，与内置库格式统一
                    String d = r.optString("date");
                    int p = d.indexOf('(');
                    if (p > 0) d = d.substring(0, p);
                    o.put("date", d);
                    o.put("week", r.optString("week"));
                    String red = r.optString("red");
                    JSONArray reds = new JSONArray();
                    for (String p2 : red.split(",")) {
                        if (!p2.trim().isEmpty()) reds.put(Integer.parseInt(p2.trim()));
                    }
                    o.put("reds", reds);
                    o.put("blue", r.optInt("blue"));
                    o.put("sales", r.optLong("sales"));
                    o.put("pool", r.optLong("poolmoney"));
                    arr.put(o);
                }
                final String s = mod.callAttr("sync_draws", arr.toString()).toString();
                runOnUiThread(() -> {
                    try {
                        JSONObject res = new JSONObject(s);
                        int added = res.optInt("写入条数");
                        int missing = res.optInt("缺失期数");
                        String last = res.optString("最新期");
                        String before = res.optString("同步前最新期");
                        if (added > 0) {
                            if (missing < 0) {
                                tvSyncHint.setText("同步成功：新增 " + added + " 期，"
                                        + "最新期号 " + last + "（原最新 " + before + "）\n"
                                        + "注意：本地数据可能过旧（超出本次拉取范围），"
                                        + "若仍有缺期，请用导入功能补全。");
                            } else {
                                tvSyncHint.setText("同步成功：新增 " + added + " 期，"
                                        + "最新期号 " + last + "（原最新 " + before + "）\n"
                                        + "统计与回测已立即生效。");
                            }
                        } else {
                            tvSyncHint.setText("已是最新：本地最新期号 " + last
                                    + " 与官网一致，无需更新。");
                        }
                        // 同步后刷新选号页状态行（期数/最新期号可能已变化）
                        if (tvStatus != null) {
                            try {
                                String st = mod.callAttr("get_stats").toString();
                                JSONObject so = new JSONObject(st);
                                tvStatus.setText("本地数据：" + so.getInt("总期数") + " 期，"
                                        + "最新期号 " + so.getString("最新期")
                                        + "（历史统计模式，全量建模）");
                            } catch (Exception ignored) { }
                        }
                    } catch (Exception e) {
                        tvSyncHint.setText("同步结果：" + s);
                    }
                    btn.setEnabled(true);
                });
            } catch (Throwable e) {
                Log.e(TAG, "sync failed", e);
                runOnUiThread(() -> {
                    tvSyncHint.setText("同步失败：" + e.getMessage());
                    btn.setEnabled(true);
                });
            }
        }).start();
    }

    /** 从福彩官网公开接口拉取最新 count 期开奖（仅拉取，不上传任何数据）。 */
    private JSONArray fetchDraws(int count) throws Exception {
        URL url = new URL("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
                + "findDrawNotice?name=ssq&issueCount=" + count
                + "&pageNo=1&pageSize=" + count);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(20000);
        conn.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
                        + "Chrome/120.0 Mobile Safari/537.36");
        conn.setRequestProperty("Referer", "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/");
        conn.setRequestProperty("Accept", "application/json, text/javascript, */*; q=0.01");
        InputStream is = conn.getInputStream();
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = is.read(buf)) > 0) bos.write(buf, 0, n);
        is.close();
        conn.disconnect();
        String body = new String(bos.toByteArray(), StandardCharsets.UTF_8);
        JSONObject obj = new JSONObject(body);
        if (obj.optInt("state") != 0) return null;
        return obj.optJSONArray("result");
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_OPEN_CSV && resultCode == RESULT_OK && data != null) {
            Uri uri = data.getData();
            if (uri == null) return;
            tvImportHint.setText("读取文件中…");
            new Thread(() -> {
                try {
                    // 把选中文件复制到缓存目录（避免流生命周期问题）
                    InputStream in = getContentResolver().openInputStream(uri);
                    if (in == null) { runOnUiThread(() -> tvImportHint.setText("无法读取该文件。")); return; }
                    File tmp = new File(getCacheDir(), "import.csv");
                    OutputStream os = new FileOutputStream(tmp);
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
                    os.close();
                    in.close();
                    final String s = mod.callAttr("import_csv", tmp.getAbsolutePath()).toString();
                    runOnUiThread(() -> tvImportHint.setText(s + "（提示：导入后数据统计/回测立即生效）"));
                } catch (Throwable e) {
                    Log.e(TAG, "csv import failed", e);
                    runOnUiThread(() -> tvImportHint.setText("导入失败：" + e));
                }
            }).start();
        }
    }
}
