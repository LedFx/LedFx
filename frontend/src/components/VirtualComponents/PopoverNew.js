import React from 'react'
import Popover from '@material-ui/core/Popover'
import Button from '@material-ui/core/Button'
import AddCircleIcon from '@material-ui/icons/AddCircle'
import TextField from '@material-ui/core/TextField'

export default function PopoverNew({ old, onSubmit, variant = 'contained', userInput = 'name', buttonText = 'Add Virtual', buttonIcon = <AddCircleIcon />, submitIcon = <AddCircleIcon /> }) {

    const [anchorEl, setAnchorEl] = React.useState(null)
    const handleClick = (event) => { setAnchorEl(event.currentTarget) }
    const handleClose = () => { setAnchorEl(null) }
    const open = Boolean(anchorEl)
    const id = open ? 'simple-popover' : undefined
    const [name, setName] = React.useState('')
    const handleChange = (event) => { setName(event.target.value) }

    return (
        <div>
            <Button aria-describedby={id} variant={variant} color="primary" onClick={handleClick}>
                {buttonText}
                {buttonIcon}
            </Button>
            <Popover
                id={id}
                open={open}
                anchorEl={anchorEl}
                onClose={handleClose}
                anchorOrigin={{
                    vertical: 'center',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'center',
                    horizontal: 'left',
                }}
            >   <div style={{ display: "flex" }}>
                    <TextField id="outlined-basic" label={userInput} value={name} onChange={handleChange} variant="outlined" />
                    <Button aria-describedby={id} variant="contained" style={{ margin: "8px" }} color="primary" onClick={() => {
                        onSubmit({ old: old, new: name })
                        setAnchorEl(null)
                    }}>
                        {submitIcon}
                    </Button>
                </div>
            </Popover>
        </div>
    );
}
