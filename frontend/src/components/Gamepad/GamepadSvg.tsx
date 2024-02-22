import { useTheme } from '@mui/material'

const GamepadSvg = ({
  pad,
  stroke = 'rgba(255,255,255,0.2)',
  stroke2 = 'rgba(255,255,255,0.5)',
  stroke3 = 'rgba(255,255,255,0.5)',
  fill = 'rgba(0,0,0,0)',
  strokeOpacity = '1',
  strokeWidth = '3',
  strokeWidth2 = '6'
}: any) => {
  const theme = useTheme()

  return (
    <svg
      width="350"
      viewBox="0 0 441 383"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g id="XBox">
        <path
          id="LOutline"
          d="M220.5 294.5C220.5 294.5 195 294.5 150 294.5C105 294.5 81.5 378.5 49.5 378.5C17.5 378.5 4 363.9 4 317.5C4 271.1 43.5 165.5 55 137.5C66.5 109.5 95.5 92.0001 128 92.0001C154 92.0001 200.5 92.0001 220.5 92.0001"
          stroke={stroke3}
          strokeWidth={strokeWidth}
          strokeOpacity={strokeOpacity}
        />
        <path
          id="ROutline"
          d="M220 294.5C220 294.5 245.5 294.5 290.5 294.5C335.5 294.5 359 378.5 391 378.5C423 378.5 436.5 363.9 436.5 317.5C436.5 271.1 397 165.5 385.5 137.5C374 109.5 345 92.0001 312.5 92.0001C286.5 92.0001 240 92.0001 220 92.0001"
          stroke={stroke3}
          strokeWidth={strokeWidth}
          strokeOpacity={strokeOpacity}
        />
        <circle
          id="LStickOutline"
          cx="113"
          cy="160"
          r="37.5"
          stroke={stroke}
          strokeOpacity={strokeOpacity}
          strokeWidth={strokeWidth}
        />
        <circle
          id="LeftStick"
          cx={113.04705882352941 + pad.axes[0] * 20}
          // eslint-disable-next-line @typescript-eslint/no-loss-of-precision
          cy={160.04705882352942 + pad.axes[1] * 20}
          r="28"
          fill={
            pad.axes[0] > 0.05 ||
            pad.axes[0] < -0.05 ||
            pad.axes[1] > 0.05 ||
            pad.axes[1] < -0.05
              ? theme.palette.primary.main
              : fill
          }
          stroke={
            pad.buttons[10].pressed
              ? `${theme.palette.primary.main}90`
              : stroke2
          }
          strokeWidth={strokeWidth}
        />
        <circle
          id="RStickOutline"
          cx="278"
          cy="238"
          r="37.5"
          stroke={stroke}
          strokeOpacity={strokeOpacity}
          strokeWidth={strokeWidth}
        />
        <circle
          id="RightStick"
          cx={278.0470588235294 + pad.axes[2] * 20}
          // eslint-disable-next-line @typescript-eslint/no-loss-of-precision
          cy={238.04705882352943 + pad.axes[3] * 20}
          r="28"
          fill={
            pad.axes[2] > 0.05 ||
            pad.axes[2] < -0.05 ||
            pad.axes[3] > 0.05 ||
            pad.axes[4] < -0.05
              ? theme.palette.primary.main
              : fill
          }
          stroke={
            pad.buttons[11].pressed ? theme.palette.primary.main : stroke2
          }
          strokeWidth={strokeWidth}
        />
        <circle
          id="DOutline"
          cx="166"
          cy="238"
          r="37.5"
          stroke={stroke}
          strokeOpacity={strokeOpacity}
          strokeWidth={strokeWidth}
        />
        <g id="DUp">
          <mask id="path-8-inside-1" fill="white">
            <path d="M177.669 222.335C180.793 219.21 180.816 213.997 176.868 212.014C176.327 211.743 175.776 211.491 175.215 211.258C172.182 210.002 168.931 209.355 165.648 209.355C162.365 209.355 159.114 210.002 156.081 211.258C155.521 211.491 154.969 211.743 154.429 212.014C150.48 213.997 150.503 219.21 153.627 222.335L159.991 228.698C163.116 231.823 168.181 231.823 171.305 228.698L177.669 222.335Z" />
          </mask>
          <path
            d="M177.669 222.335C180.793 219.21 180.816 213.997 176.868 212.014C176.327 211.743 175.776 211.491 175.215 211.258C172.182 210.002 168.931 209.355 165.648 209.355C162.365 209.355 159.114 210.002 156.081 211.258C155.521 211.491 154.969 211.743 154.429 212.014C150.48 213.997 150.503 219.21 153.627 222.335L159.991 228.698C163.116 231.823 168.181 231.823 171.305 228.698L177.669 222.335Z"
            fill={fill}
            stroke={
              pad.buttons[12].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-8-inside-1)"
          />
        </g>
        <g id="DRight">
          <mask id="path-9-inside-2" fill="white">
            <path d="M181.447 249.669C184.571 252.793 189.785 252.816 191.768 248.868C192.039 248.327 192.291 247.776 192.523 247.215C193.78 244.182 194.426 240.931 194.426 237.648C194.426 234.365 193.78 231.114 192.523 228.081C192.291 227.521 192.039 226.969 191.768 226.429C189.785 222.48 184.571 222.503 181.447 225.627L175.083 231.991C171.959 235.116 171.959 240.181 175.083 243.305L181.447 249.669Z" />
          </mask>
          <path
            d="M181.447 249.669C184.571 252.793 189.785 252.816 191.768 248.868C192.039 248.327 192.291 247.776 192.523 247.215C193.78 244.182 194.426 240.931 194.426 237.648C194.426 234.365 193.78 231.114 192.523 228.081C192.291 227.521 192.039 226.969 191.768 226.429C189.785 222.48 184.571 222.503 181.447 225.627L175.083 231.991C171.959 235.116 171.959 240.181 175.083 243.305L181.447 249.669Z"
            fill={fill}
            stroke={
              pad.buttons[15].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-9-inside-2)"
          />
        </g>
        <g id="DDown">
          <mask id="path-10-inside-3" fill="white">
            <path d="M154.113 253.447C150.989 256.571 150.966 261.785 154.914 263.767C155.455 264.039 156.006 264.291 156.566 264.523C159.6 265.78 162.85 266.426 166.134 266.426C169.417 266.426 172.667 265.78 175.701 264.523C176.261 264.291 176.812 264.039 177.353 263.767C181.301 261.785 181.279 256.571 178.154 253.447L171.79 247.083C168.666 243.959 163.601 243.959 160.477 247.083L154.113 253.447Z" />
          </mask>
          <path
            d="M154.113 253.447C150.989 256.571 150.966 261.785 154.914 263.767C155.455 264.039 156.006 264.291 156.566 264.523C159.6 265.78 162.85 266.426 166.134 266.426C169.417 266.426 172.667 265.78 175.701 264.523C176.261 264.291 176.812 264.039 177.353 263.767C181.301 261.785 181.279 256.571 178.154 253.447L171.79 247.083C168.666 243.959 163.601 243.959 160.477 247.083L154.113 253.447Z"
            fill={fill}
            stroke={
              pad.buttons[13].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-10-inside-3)"
          />
        </g>
        <g id="DLeft">
          <mask id="path-11-inside-4" fill="white">
            <path d="M150.335 226.113C147.21 222.989 141.997 222.966 140.014 226.914C139.743 227.455 139.491 228.006 139.258 228.566C138.002 231.6 137.355 234.85 137.355 238.134C137.355 241.417 138.002 244.667 139.258 247.701C139.491 248.261 139.743 248.812 140.014 249.353C141.997 253.301 147.21 253.279 150.335 250.154L156.698 243.79C159.823 240.666 159.823 235.601 156.698 232.477L150.335 226.113Z" />
          </mask>
          <path
            d="M150.335 226.113C147.21 222.989 141.997 222.966 140.014 226.914C139.743 227.455 139.491 228.006 139.258 228.566C138.002 231.6 137.355 234.85 137.355 238.134C137.355 241.417 138.002 244.667 139.258 247.701C139.491 248.261 139.743 248.812 140.014 249.353C141.997 253.301 147.21 253.279 150.335 250.154L156.698 243.79C159.823 240.666 159.823 235.601 156.698 232.477L150.335 226.113Z"
            fill={fill}
            stroke={
              pad.buttons[14].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-11-inside-4)"
          />
        </g>
        <circle
          id="BOutline"
          cx="329"
          cy="160"
          r="37.5"
          stroke={stroke}
          strokeOpacity={strokeOpacity}
          strokeWidth={strokeWidth}
        />
        <g id="BTop">
          <mask id="path-13-inside-5" fill="white">
            <path d="M340.669 144.335C343.793 141.21 343.816 135.997 339.868 134.014C339.327 133.743 338.776 133.491 338.215 133.258C335.182 132.002 331.931 131.355 328.648 131.355C325.365 131.355 322.114 132.002 319.081 133.258C318.521 133.491 317.969 133.743 317.429 134.014C313.48 135.997 313.503 141.21 316.627 144.335L322.991 150.698C326.116 153.823 331.181 153.823 334.305 150.698L340.669 144.335Z" />
          </mask>
          <path
            d="M340.669 144.335C343.793 141.21 343.816 135.997 339.868 134.014C339.327 133.743 338.776 133.491 338.215 133.258C335.182 132.002 331.931 131.355 328.648 131.355C325.365 131.355 322.114 132.002 319.081 133.258C318.521 133.491 317.969 133.743 317.429 134.014C313.48 135.997 313.503 141.21 316.627 144.335L322.991 150.698C326.116 153.823 331.181 153.823 334.305 150.698L340.669 144.335Z"
            fill={fill}
            stroke={
              pad.buttons[3].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-13-inside-5)"
          />
        </g>
        <g id="BRight">
          <mask id="path-14-inside-6" fill="white">
            <path d="M344.447 171.669C347.571 174.793 352.785 174.816 354.768 170.868C355.039 170.327 355.291 169.776 355.523 169.215C356.78 166.182 357.426 162.931 357.426 159.648C357.426 156.365 356.78 153.114 355.523 150.081C355.291 149.521 355.039 148.969 354.768 148.429C352.785 144.48 347.571 144.503 344.447 147.627L338.083 153.991C334.959 157.116 334.959 162.181 338.083 165.305L344.447 171.669Z" />
          </mask>
          <path
            d="M344.447 171.669C347.571 174.793 352.785 174.816 354.768 170.868C355.039 170.327 355.291 169.776 355.523 169.215C356.78 166.182 357.426 162.931 357.426 159.648C357.426 156.365 356.78 153.114 355.523 150.081C355.291 149.521 355.039 148.969 354.768 148.429C352.785 144.48 347.571 144.503 344.447 147.627L338.083 153.991C334.959 157.116 334.959 162.181 338.083 165.305L344.447 171.669Z"
            fill={fill}
            stroke={
              pad.buttons[1].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-14-inside-6)"
          />
        </g>
        <g id="BBottom">
          <mask id="path-15-inside-7" fill="white">
            <path d="M317.113 175.447C313.989 178.571 313.966 183.785 317.914 185.767C318.455 186.039 319.006 186.291 319.566 186.523C322.6 187.78 325.85 188.426 329.134 188.426C332.417 188.426 335.667 187.78 338.701 186.523C339.261 186.291 339.812 186.039 340.353 185.767C344.301 183.785 344.279 178.571 341.154 175.447L334.79 169.083C331.666 165.959 326.601 165.959 323.477 169.083L317.113 175.447Z" />
          </mask>
          <path
            d="M317.113 175.447C313.989 178.571 313.966 183.785 317.914 185.767C318.455 186.039 319.006 186.291 319.566 186.523C322.6 187.78 325.85 188.426 329.134 188.426C332.417 188.426 335.667 187.78 338.701 186.523C339.261 186.291 339.812 186.039 340.353 185.767C344.301 183.785 344.279 178.571 341.154 175.447L334.79 169.083C331.666 165.959 326.601 165.959 323.477 169.083L317.113 175.447Z"
            fill={fill}
            stroke={
              pad.buttons[0].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-15-inside-7)"
          />
        </g>
        <g id="BLeft">
          <mask id="path-16-inside-8" fill="white">
            <path d="M313.335 148.113C310.21 144.989 304.997 144.966 303.014 148.914C302.743 149.455 302.491 150.006 302.258 150.566C301.002 153.6 300.355 156.851 300.355 160.134C300.355 163.417 301.002 166.668 302.258 169.701C302.491 170.261 302.743 170.812 303.014 171.353C304.997 175.301 310.21 175.279 313.335 172.154L319.698 165.79C322.823 162.666 322.823 157.601 319.698 154.477L313.335 148.113Z" />
          </mask>
          <path
            d="M313.335 148.113C310.21 144.989 304.997 144.966 303.014 148.914C302.743 149.455 302.491 150.006 302.258 150.566C301.002 153.6 300.355 156.851 300.355 160.134C300.355 163.417 301.002 166.668 302.258 169.701C302.491 170.261 302.743 170.812 303.014 171.353C304.997 175.301 310.21 175.279 313.335 172.154L319.698 165.79C322.823 162.666 322.823 157.601 319.698 154.477L313.335 148.113Z"
            fill={fill}
            stroke={
              pad.buttons[2].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth2}
            mask="url(#path-16-inside-8)"
          />
        </g>
        <g id="LMeta">
          <circle
            cx="185"
            cy="162"
            r="10"
            fill={fill}
            stroke={
              pad.buttons[8].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth}
          />
        </g>
        <g id="MMeta">
          <circle
            cx="222"
            cy="200"
            r="12"
            fill={fill}
            stroke={
              pad.buttons[16].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth}
          />
        </g>
        <g id="RMeta">
          <circle
            cx="259"
            cy="162"
            r="10"
            fill={fill}
            stroke={
              pad.buttons[9].pressed ? theme.palette.primary.main : stroke2
            }
            strokeWidth={strokeWidth}
          />
        </g>
        <rect
          id="L1"
          x="111.5"
          y="61.5"
          width="41"
          height="13"
          rx="6.5"
          fill={fill}
          stroke={pad.buttons[4].pressed ? theme.palette.primary.main : stroke2}
          strokeWidth={strokeWidth}
        />
        <rect
          id="R1"
          x="289.5"
          y="61.5"
          width="41"
          height="13"
          rx="6.5"
          fill={fill}
          stroke={pad.buttons[5].pressed ? theme.palette.primary.main : stroke2}
          strokeWidth={strokeWidth}
        />
        <path
          id="L2"
          d="M152.5 37C152.5 41.1421 149.142 44.5 145 44.5H132C127.858 44.5 124.5 41.1421 124.5 37V16.5C124.5 8.76801 130.768 2.5 138.5 2.5C146.232 2.5 152.5 8.76801 152.5 16.5V37Z"
          fill={fill}
          stroke={pad.buttons[6].pressed ? theme.palette.primary.main : stroke2}
          strokeWidth={strokeWidth}
        />
        <path
          id="R2"
          d="M317.5 37C317.5 41.1421 314.142 44.5 310 44.5H297C292.858 44.5 289.5 41.1421 289.5 37V16.5C289.5 8.76801 295.768 2.5 303.5 2.5C311.232 2.5 317.5 8.76801 317.5 16.5V37Z"
          fill={fill}
          stroke={pad.buttons[7].pressed ? theme.palette.primary.main : stroke2}
          strokeWidth={strokeWidth}
        />
        <line
          x1="30"
          y1="210"
          x2="130"
          y2="300"
          strokeWidth={strokeWidth}
          stroke="rgba(0,0,0,0.1)"
          opacity="0.3"
        />
        <line
          x1="411"
          y1="210"
          x2="311"
          y2="300"
          strokeWidth={strokeWidth}
          stroke="rgba(0,0,0,0.1)"
          opacity="0.3"
        />
      </g>
    </svg>
  )
}

export default GamepadSvg
