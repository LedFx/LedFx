import { styled } from '@mui/material/styles'
import Typography from '@mui/material/Typography'
import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  spWrapper: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    '@media (max-width: 720px)': {
      '&&': {
        flexDirection: 'column'
      }
    },
    '&.small': {
      '&&': {
        flexDirection: 'column'
      }
    }
  },
  spDeskVol: {
    marginBottom: 1,
    flexDirection: 'column',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    width: '26%',
    '&&': { marginBottom: 0, alignSelf: 'stretch' },
    '@media (max-width: 960px)': {
      '&&': {
        display: 'none'
      }
    },
    '&.medium': {
      '&&': {
        display: 'none'
      }
    },
    '&&.small': {
      width: '100%',
      maxWidth: 400,
      margin: '0 auto',
      alignItems: 'center'
    }
  },
  SpControlstyles: {
    display: 'flex',
    flexDirection: 'column',
    alignSelf: 'stretch',
    justifyContent: 'space-between',
    padding: '7px 0 4px 0',
    '@media (max-width: 960px)': {
      '&&': {
        width: '50%'
      }
    },
    '&.medium': {
      '&&': {
        width: '50%'
      }
    },
    '@media (max-width: 720px)': {
      '&&': {
        width: '100%'
      }
    },
    '&&.small': {
      width: '100%',
      maxWidth: 400,
      margin: '0 auto'
    }
  },
  spTrack: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-start',
    width: '26%',
    '@media (max-width: 960px)': {
      '&&': {
        width: '50%'
      }
    },
    '&.medium': {
      '&&': {
        width: '50%'
      }
    },
    '@media (max-width: 720px)': {
      '&&': {
        width: '100%'
      }
    },
    '&&.small': {
      width: '100%'
    }
  },
  Widget: {
    padding: 16,
    borderRadius: 16,
    width: '100%',
    maxWidth: '100%',
    margin: 'auto',
    position: 'relative',
    zIndex: 1,
    backgroundColor: '#2229',
    backdropFilter: 'blur(40px)',
    '@media (max-width: 720px)': {
      '&&': {
        width: 400
      }
    },
    '&.small': {
      '&&': {
        width: 400
      }
    }
  },
  albumImg: {
    '@media (max-width: 720px)': {
      '&&': {
        height: 80,
        width: 80,
        margin: 10
      }
    },
    '&.small': {
      '&&': {
        height: 80,
        width: 80,
        margin: 10
      }
    }
  }
}))

export const CoverImage = styled('div')({
  width: 100,
  height: 100,
  objectFit: 'cover',
  overflow: 'hidden',
  flexShrink: 0,
  borderRadius: 8,
  backgroundColor: 'rgba(0,0,0,0.08)',
  '& > img': {
    width: '100%'
  }
})

export const TinyText = styled(Typography)({
  fontSize: '0.75rem',
  opacity: 0.38,
  fontWeight: 500,
  letterSpacing: 0.2
})

export const PosSliderStyles = {
  color: '#fff',
  height: 4,
  '& .MuiSlider-track': {
    border: 'none'
  },
  '& .MuiSlider-thumb': {
    width: 12,
    height: 12,
    transition: '0.3s cubic-bezier(.47,1.64,.41,.8)',
    '&:before': {
      boxShadow: '0 2px 12px 0 rgba(0,0,0,0.4)'
    },
    '&:hover, &.Mui-focusVisible': {
      boxShadow: '0px 0px 0px 8px rgb(255 255 255 / 16%)'
    },
    '&.Mui-active': {
      width: 20,
      height: 20
    }
  },
  '& .MuiSlider-rail': {
    opacity: 0.28
  },
  '& .MuiSlider-mark': {
    backgroundColor: '#bfbfbf',
    height: 8,
    width: 2,
    '&.MuiSlider-markActive': {
      opacity: 1,
      backgroundColor: 'currentColor'
    }
  },
  // '& span[aria-hidden].MuiSlider-markLabel:nth-child(4n)': {
  //   opacity: 0,
  //   color: '#f00',
  // },
  '& .MuiSlider-markLabel': {
    opacity: 0,
    color: '#aaa'
  },
  '& .MuiSlider-mark:hover + .MuiSlider-markLabel, & .MuiSlider-markLabel:hover':
    {
      opacity: 1
    },
  '& .MuiSlider-markActive + .MuiSlider-markLabel': {
    opacity: 1
  }
}

export const VolSliderStyles = {
  color: '#fff',
  '& .MuiSlider-track': {
    border: 'none'
  },
  '& .MuiSlider-thumb': {
    width: 16,
    height: 16,
    backgroundColor: '#fff',
    '&:before': {
      boxShadow: '0 4px 8px rgba(0,0,0,0.4)'
    },
    '&:hover, &.Mui-focusVisible, &.Mui-active': {
      boxShadow: 'none'
    }
  }
}

export default useStyles
