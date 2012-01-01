const struct canon_usb_control_cmdstruct canon_usb_control_cmd[] =
        {
        /* COMMAND NAME                         Description            Value   CmdLen ReplyLen */
        { CANON_USB_CONTROL_INIT, "Camera control init", 0x00, 0x18, 0x1c }, /* load 0x00, 0x00 */
                { CANON_USB_CONTROL_SHUTTER_RELEASE, "Release shutter", 0x04,
                        0x18, 0x1c }, /* load 0x04, 0x00 */
                { CANON_USB_CONTROL_SET_PARAMS, "Set release params", 0x07,
                        0x3c, 0x1c }, /* ?? */
                { CANON_USB_CONTROL_SET_TRANSFER_MODE, "Set transfer mode",
                        0x09, 0x1c, 0x1c }, /* load (0x09, 0x04, 0x03) or (0x09, 0x04, 0x02000003) */
                { CANON_USB_CONTROL_GET_PARAMS, "Get release params", 0x0a,
                        0x18, 0x4c }, /* load 0x0a, 0x00 */
                { CANON_USB_CONTROL_GET_ZOOM_POS, "Get zoom position", 0x0b,
                        0x18, 0x20 }, /* load 0x0b, 0x00 */
                { CANON_USB_CONTROL_SET_ZOOM_POS, "Set zoom position", 0x0c,
                        0x1c, 0x1c }, /* load 0x0c, 0x04, 0x01 (or 0x0c, 0x04, 0x0b) (or 0x0c, 0x04, 0x0a) or (0x0c, 0x04, 0x09) or (0x0c, 0x04, 0x08) or (0x0c, 0x04, 0x07) or (0x0c, 0x04, 0x06) or (0x0c, 0x04, 0x00) */
                { CANON_USB_CONTROL_GET_AVAILABLE_SHOT, "Get available shot",
                        0x0d, 0x18, 0x20 }, { CANON_USB_CONTROL_GET_CUSTOM_FUNC,
                        "Get custom func.", 0x0f, 0x22, 0x26 }, {
                        CANON_USB_CONTROL_GET_EXT_PARAMS_SIZE,
                        "Get ext. release params size", 0x10, 0x1c, 0x20 }, /* load 0x10, 0x00 */
                { CANON_USB_CONTROL_GET_EXT_PARAMS, "Get ext. release params",
                        0x12, 0x1c, 0x2c }, /* load 0x12, 0x04, 0x10 */
                { CANON_USB_CONTROL_SET_EXT_PARAMS, "Set extended params", 0x13,
                        0x15, 0x1c }, /* based on EOS 20D */

                { CANON_USB_CONTROL_EXIT, "Exit release control", 0x01, 0x18,
                        0x1c },
                /* New subcodes for new version of protocol */
                { CANON_USB_CONTROL_UNKNOWN_1, "Unknown remote subcode", 0x1b,
                        0x08, 0x5e }, { CANON_USB_CONTROL_UNKNOWN_2,
                        "Unknown remote subcode", 0x1c, 0x00, 0x00 },
                /* unobserved, commands present in canon headers defines, but need more usb snoops to get reply lengths */
                { CANON_USB_CONTROL_VIEWFINDER_START, "Start viewfinder", 0x02,
                        0x00, 0x00 }, { CANON_USB_CONTROL_VIEWFINDER_STOP,
                        "Stop viewfinder", 0x03, 0x00, 0x00 }, {
                        CANON_USB_CONTROL_SET_CUSTOM_FUNC, "Set custom func.",
                        0x0e, 0x00, 0x00 }, {
                        CANON_USB_CONTROL_GET_EXT_PARAMS_VER,
                        "Get extended params version", 0x11, 0x00, 0x00 }, {
                        CANON_USB_CONTROL_SELECT_CAM_OUTPUT,
                        "Select camera output", 0x14, 0x00, 0x00 }, /* LCD (0x1), Video out (0x2), or OFF (0x3) */
                { CANON_USB_CONTROL_DO_AE_AF_AWB, "Do AE, AF, and AWB", 0x15,
                        0x00, 0x00 }, { 0, NULL, 0, 0, 0 } };
