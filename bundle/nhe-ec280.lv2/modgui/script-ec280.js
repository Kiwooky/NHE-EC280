function (event, funcs) {
    // EC 280 face script (no dollar signs: this text sits in a make define).
    //
    // Button banks: each bank is one port holding a bitmask (1-15).
    //   Tap = that button only (radio, like the hardware).
    //   Hold ~0.5 s, or shift-click = add/remove it (the "press together" hack).
    //   The last button down cannot be removed, so a bank is never empty.
    // Switches (Tail, Range, Echo/Reverb): one press flips 0 <-> 1. They are
    // driven here rather than by mod-ui's filmstrip click, which did not flip
    // back from 1 to 0 on the Duo.
    var HOLD_MS = 500;
    var data = event.data;
    var icon = event.icon;
    var BANKS = { echo_taps: true, hall_taps: true };
    var SWITCHES = { tails: true, range: true, mode: true };

    function draw(symbol, value) {
        var b, el;
        if (BANKS[symbol]) {
            var m = Math.round(value);
            data[symbol] = m;
            for (b = 0; b < 4; b++) {
                el = icon.find('[ec-bank="' + symbol + '"][ec-bit="' + b + '"]');
                if (m & (1 << b)) el.addClass('down'); else el.removeClass('down');
            }
        } else if (SWITCHES[symbol]) {
            var lit = value > 0.5;
            data[symbol] = lit ? 1 : 0;
            el = icon.find('[ec-switch="' + symbol + '"]');
            if (lit) el.addClass('lit'); else el.removeClass('lit');
        }
    }

    function send(symbol, value) {
        funcs.set_port_value(symbol, value);
        draw(symbol, value);   // plugin JS gets no change event for its own sets
    }

    function setMask(symbol, m) {
        if (m < 1 || m > 15 || m === data[symbol]) return;
        send(symbol, m);
    }

    function pressBank(el, e) {
        var symbol = el.attr('ec-bank');
        var bit = parseInt(el.attr('ec-bit'), 10);
        var held = false;

        if (e.shiftKey) {
            setMask(symbol, data[symbol] ^ (1 << bit));
            return;
        }
        var timer = setTimeout(function () {
            held = true;
            setMask(symbol, data[symbol] ^ (1 << bit));   // fires while still held
        }, HOLD_MS);

        function release() {
            jQuery(document).off('mouseup touchend touchcancel', release);
            clearTimeout(timer);
            if (!held) setMask(symbol, 1 << bit);
        }
        jQuery(document).on('mouseup touchend touchcancel', release);
    }

    function pressSwitch(el) {
        var symbol = el.attr('ec-switch');
        send(symbol, data[symbol] ? 0 : 1);
    }

    // One handler for mouse and touch; ignore the mouse events a touch screen
    // emulates after a touch, and anything but the left button.
    function bindPress(el, fn) {
        el.on('touchstart', function (e) {
            e.preventDefault();
            e.stopPropagation();
            data.lastTouch = Date.now();
            fn(el, e);
        });
        el.on('mousedown', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (data.lastTouch && Date.now() - data.lastTouch < 1000) return;
            if (e.which && e.which !== 1) return;
            fn(el, e);
        });
    }

    if (event.type === 'start') {
        for (var i = 0; i < event.ports.length; i++) {
            draw(event.ports[i].symbol, event.ports[i].value);
        }
        icon.find('[ec-bank]').each(function () { bindPress(jQuery(this), pressBank); });
        icon.find('[ec-switch]').each(function () { bindPress(jQuery(this), pressSwitch); });
    } else if (event.type === 'change') {
        draw(event.symbol, event.value);
    }
}
