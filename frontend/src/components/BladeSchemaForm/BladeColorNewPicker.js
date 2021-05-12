import React, { useCallback, useRef } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Popper from '@material-ui/core/Popper';
import ClickAwayListener from '@material-ui/core/ClickAwayListener';
import useClickOutside from 'views/Advanced/useClickOutside';
import { HslStringColorPicker } from 'react-colorful';
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

const BladeColorNewPicker = ({ sendColor, col, clr }) => {
    const classes = useStyles();
    const popover = useRef();
    const [anchorEl, setAnchorEl] = React.useState(null);
    const [colorNew, setColorNew] = React.useState('hsl(0, 100%, 25%)');
    const handleClick = event => {
        setAnchorEl(anchorEl ? null : event.currentTarget);
    };
    const handleColorChange = e => {
        setColorNew(e);
        sendColor(e);
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
                style={{ backgroundColor: colorNew.replaceAll('"', '').replaceAll("'", '') }}
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
                        <HslStringColorPicker color={colorNew} onChange={handleColorChange} />
                        {/* {Object.keys(coloring).map(c => (
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
                        ))} */}
                    </div>
                </Popper>
            </ClickAwayListener>
        </div>
    );
};
export default BladeColorNewPicker;
