import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Popover from '@material-ui/core/Popover';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import DeleteIcon from '@material-ui/icons/Delete';
import CloseIcon from '@material-ui/icons/Close';
import CheckIcon from '@material-ui/icons/Check';

const useStyles = makeStyles(theme => ({
    typography: {
        padding: theme.spacing(2),
    },
}));

export default function PopoverSure({
    onConfirm,
    variant = 'contained',
    color = 'secondary',
    label,
    text = 'Are you sure?',
    direction = 'left',
    vertical = 'center',
    size = 'small',
    icon = <DeleteIcon />,
    className,
    startIcon,
    style = {},
}) {
    const classes = useStyles();
    const [anchorEl, setAnchorEl] = React.useState(null);
    const handleClick = event => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };
    const open = Boolean(anchorEl);
    const id = open ? 'simple-popover' : undefined;

    return (
        <div style={{ display: 'initial' }}>
            <Button
                aria-describedby={id}
                variant={variant}
                color={color}
                onClick={handleClick}
                size={size}
                className={className}
                style={style}
                startIcon={startIcon}
            >
                {label}
                {!startIcon && icon}
            </Button>
            <Popover
                id={id}
                open={open}
                anchorEl={anchorEl}
                onClose={handleClose}
                anchorOrigin={{
                    vertical: vertical,
                    horizontal: direction,
                }}
                transformOrigin={{
                    vertical: vertical,
                    horizontal: direction === 'center' ? 'center' : 'right',
                }}
            >
                {' '}
                <div style={{ display: 'flex' }}>
                    <Typography className={classes.typography}>{text}</Typography>
                    <Button
                        aria-describedby={id}
                        variant="contained"
                        color="primary"
                        onClick={() => {
                            onConfirm();
                            setAnchorEl(null);
                        }}
                    >
                        <CheckIcon />
                    </Button>
                    <Button
                        aria-describedby={id}
                        variant="contained"
                        color="default"
                        onClick={() => {
                            setAnchorEl(null);
                        }}
                    >
                        <CloseIcon />
                    </Button>
                </div>
            </Popover>
        </div>
    );
}
