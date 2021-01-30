import React from 'react';
import { useDispatch } from 'react-redux';
import { makeStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
import Dialog from '@material-ui/core/Dialog';
import AppBar from '@material-ui/core/AppBar';
import Toolbar from '@material-ui/core/Toolbar';
import IconButton from '@material-ui/core/IconButton';
import Typography from '@material-ui/core/Typography';
import CloseIcon from '@material-ui/icons/Close';
import Slide from '@material-ui/core/Slide';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import SaveIcon from '@material-ui/icons/Save';
import AddSegmentDialog from './AddSegmentDialog';
import Segment from './Segment';
import { updateDisplayConfig } from 'modules/displays';

const useStyles = makeStyles(theme => ({
    appBar: {
        position: 'relative',
        marginBottom: '1rem',
        background: theme.palette.background.default,
        color: theme.palette.text.primary,
    },
    title: {
        marginLeft: theme.spacing(2),
        flex: 1,
    },
    dialog: {
        background: theme.palette.background.default,
    },
}));

const Transition = React.forwardRef(function Transition(props, ref) {
    return <Slide direction="up" ref={ref} {...props} />;
});

export default function FullScreenDialog({ display, icon, className }) {
    const dispatch = useDispatch();
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);

    const handleClickOpen = () => {
        setOpen(true);
    };

    const handleClose = () => {
        setOpen(false);
    };

    const handleSave = () => {
        dispatch(updateDisplayConfig({ id: display.id, data: display.segments }));
        setOpen(false);
    };

    return (
        <>
            <Button
                variant="contained"
                color={'default'}
                onClick={handleClickOpen}
                size="small"
                className={className}
            >
                {icon || <AddCircleIcon />}
            </Button>
            <Dialog fullScreen open={open} onClose={handleClose} TransitionComponent={Transition}>
                <AppBar className={classes.appBar}>
                    <Toolbar>
                        <IconButton
                            edge="start"
                            color="inherit"
                            onClick={handleClose}
                            aria-label="close"
                        >
                            <CloseIcon />
                        </IconButton>
                        <Typography variant="h6" className={classes.title}>
                            {display.config.name}{' '}
                        </Typography>
                        <Button
                            autoFocus
                            color="primary"
                            variant="contained"
                            endIcon={<SaveIcon />}
                            onClick={handleSave}
                        >
                            save
                        </Button>
                    </Toolbar>
                </AppBar>
                <div
                    style={{
                        display: 'flex',
                        borderBottom: '1px dashed #aaa',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        margin: '0 1rem',
                    }}
                >
                    <Typography variant="caption">Segments-Settings</Typography>
                </div>
                {display.segments.length > 0 &&
                    display.segments.map((s, i) => (
                        <Segment s={s} i={i} key={i} display={display} />
                    ))}

                <AddSegmentDialog display={display} />
            </Dialog>
        </>
    );
}
