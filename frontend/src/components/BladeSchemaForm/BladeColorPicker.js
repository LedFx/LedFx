import React, { useCallback, useRef } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Popper from '@material-ui/core/Popper';
import ClickAwayListener from '@material-ui/core/ClickAwayListener';
import useClickOutside from 'views/Advanced/useClickOutside';
const useStyles = makeStyles(theme => ({
    paper: {
        border: '1px solid',
        display: 'flex',
        flexWrap: 'wrap',
        maxWidth: '320px',
        padding: theme.spacing(1),
        backgroundColor: theme.palette.background.paper,
    },
    picker: {
        width: '150px',
        height: '30px',
        margin: '15px 10px 10px 10px',
        borderRadius: '10px',
        cursor: 'pointer',
        border: `1px solid #fff`,
    },
    wrapper: {
        border: `1px solid #999`,
        borderRadius: '10px',
        position: 'relative',
        margin: '0.5rem',
        '& > label': {
            top: '-0.7rem',
            display: 'flex',
            alignItems: 'center',
            left: '1rem',
            padding: '0 0.3rem',
            position: 'absolute',
            fontVariant: 'all-small-caps',
            backgroundColor: theme.palette.background.paper,
            boxSizing: 'border-box',
        },
    },
}));

const coloring = {
    red: 'rgb(255, 0, 0)',
    'orange-deep': 'rgb(255, 40, 0)',
    orange: 'rgb(255, 120, 0)',
    yellow: 'rgb(255, 200, 0)',
    'yellow-acid': 'rgb(160, 255, 0)',
    green: 'rgb(0, 255, 0)',
    'green-forest': 'rgb(34, 139, 34)',
    'green-spring': 'rgb(0, 255, 127)',
    'green-teal': 'rgb(0, 128, 128)',
    'green-turquoise': 'rgb(0, 199, 140)',
    'green-coral': 'rgb(0, 255, 50)',
    cyan: 'rgb(0, 255, 255)',
    blue: 'rgb(0, 0, 255)',
    'blue-light': 'rgb(65, 105, 225)',
    'blue-navy': 'rgb(0, 0, 128)',
    'blue-aqua': 'rgb(0, 255, 255)',
    purple: 'rgb(128, 0, 128)',
    pink: 'rgb(255, 0, 178)',
    magenta: 'rgb(255, 0, 255)',
    black: 'rgb(0, 0, 0)',
    white: 'rgb(255, 255, 255)',
    brown: 'rgb(139, 69, 19)',
    gold: 'rgb(255, 215, 0)',
    hotpink: 'rgb(255, 105, 180)',
    lightblue: 'rgb(173, 216, 230)',
    lightgreen: 'rgb(152, 251, 152)',
    lightpink: 'rgb(255, 182, 193)',
    lightyellow: 'rgb(255, 255, 224)',
    maroon: 'rgb(128, 0, 0)',
    mint: 'rgb(189, 252, 201)',
    olive: 'rgb(85, 107, 47)',
    peach: 'rgb(255, 100, 100)',
    plum: 'rgb(221, 160, 221)',
    sepia: 'rgb(94, 38, 18)',
    skyblue: 'rgb(135, 206, 235)',
    steelblue: 'rgb(70, 130, 180)',
    tan: 'rgb(210, 180, 140)',
    violetred: 'rgb(208, 32, 144)',
};

const BladeColorPicker = ({ sendColor, col, clr }) => {
    const classes = useStyles();
    const popover = useRef();
    const [anchorEl, setAnchorEl] = React.useState(null);

    const handleClick = event => {
        setAnchorEl(anchorEl ? null : event.currentTarget);
    };
    // const handleClickaway = event => {
    //     console.log(anchorEl);
    //     if (!anchorEl) {
    //         setAnchorEl(null);
    //     }
    //     // setAnchorEl(anchorEl ? null : event.currentTarget);
    // };
    const handleClose = useCallback(() => {
        setAnchorEl(null);
    }, []);
    useClickOutside(popover, handleClose);
    const open = Boolean(anchorEl);
    const id = open ? 'simple-popper' : undefined;

    return (
        <div className={classes.wrapper}>
            <label>
                {/* <Palette /> */}
                {clr.replaceAll('_', ' ')}
            </label>
            <div
                className={classes.picker}
                style={{ background: coloring[col] }}
                aria-describedby={id}
                onClick={handleClick}
            ></div>
            <ClickAwayListener
                onClickAway={() => {
                    // console.log('anchorEl');
                    // setAnchorEl(null);
                }}
            >
                <Popper id={id} open={open} onClose={handleClose} anchorEl={anchorEl} ref={popover}>
                    <div className={classes.paper}>
                        {Object.keys(coloring).map(c => (
                            <div
                                key={c}
                                style={{
                                    width: c === col ? '22px' : '20px',
                                    height: c === col ? '22px' : '20px',
                                    margin: c === col ? '4px' : '5px',
                                    borderRadius: '5px',
                                    cursor: 'pointer',
                                    background: coloring[c],
                                    border: c === col ? `2px solid #000` : `1px solid #fff`,
                                }}
                                onClick={() => sendColor(c)}
                            ></div>
                        ))}
                    </div>
                </Popper>
            </ClickAwayListener>
        </div>
    );
};
export default BladeColorPicker;
