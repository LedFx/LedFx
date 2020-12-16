import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Popover from '@material-ui/core/Popover';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import DeleteIcon from "@material-ui/icons/Delete";
import CloseIcon from "@material-ui/icons/Close";

const useStyles = makeStyles((theme) => ({
    typography: {
        padding: theme.spacing(2),
    },
}));

export default function SimplePopover({ onDeleteVitem, listItem }) {
    const classes = useStyles();
    const [anchorEl, setAnchorEl] = React.useState(null);

    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const open = Boolean(anchorEl);
    const id = open ? 'simple-popover' : undefined;

    return (
        <div>
            <Button aria-describedby={id} variant="contained" color="secondary" onClick={handleClick}>
                <DeleteIcon />
            </Button>
            <Popover
                id={id}
                open={open}
                anchorEl={anchorEl}
                onClose={handleClose}
                anchorOrigin={{
                    vertical: 'center',
                    horizontal: 'left',
                }}
                transformOrigin={{
                    vertical: 'center',
                    horizontal: 'right',
                }}
            >   <div style={{ display: "flex" }}>
                    <Typography className={classes.typography}>Are you sure?</Typography>
                    <Button aria-describedby={id} variant="contained" color="inherit" onClick={() => { onDeleteVitem(listItem) }}>
                        <DeleteIcon />
                    </Button>
                    <Button aria-describedby={id} variant="contained" color="default" onClick={() => { setAnchorEl(null) }}>
                        <CloseIcon />
                    </Button>
                </div>
            </Popover>
        </div>
    );
}
