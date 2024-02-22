/* eslint-disable prettier/prettier */
import { PaletteMode } from '@mui/material'
import { createTheme, Theme } from '@mui/material/styles'
import isElectron from 'is-electron'

declare module '@mui/styles' {
  type DefaultTheme = Theme
}
declare module '@mui/material/styles' {
  interface Palette {
    accent: Palette['primary']
  }
  interface PaletteOptions {
    accent: PaletteOptions['primary']
  }
}

export const common = {
  typography: {
    fontFamily: '"Nunito", "Roboto", "Helvetica", "Arial", sans-serif',
    fontSize: 14,
    fontWeightRegular: 400
  },
  components: {
    MuiButton: {
      defaultProps: {
        // eslint-disable-next-line prettier/prettier
        color: 'inherit' as 'error' | 'success' | 'warning' | 'info' | 'inherit' | 'primary' | 'secondary' | undefined,
        variant: 'outlined' as 'contained' | 'outlined' | 'text' | undefined,
        size: 'small' as 'small' | 'medium' | 'large'
      },
      styleOverrides: {
        root: {
          borderColor: '#bbb'
        }
      }
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined' as 'filled' | 'outlined' | 'standard' | undefined
      }
    },
    MuiSelect: {
      defaultProps: {
        variant: 'standard' as 'filled' | 'outlined' | 'standard' | undefined
        // inputProps: {
        //   disableUnderline: true,
        // },
      }
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundImage: 'none'
        }
      }
    },
    MuiAccordion: {
      styleOverrides: {
        root: {
          backgroundImage: 'none'
        }
      }
    },
    MuiChip: {
      defaultProps: {
        variant: 'outlined' as 'outlined' | 'filled' | undefined,
        sx: {
          m: 0.3
        }
      }
    },
    MuiBottomNavigationAction: {
      defaultProps: {
        sx: { minWidth: 50, color: '#a1998e' }
      }
    }
  }
}

export const BladeDarkGreenTheme = {
  palette: {
    mode: 'dark' as PaletteMode | undefined,
    primary: {
      main: '#2BDE6A'
    },
    secondary: {
      main: '#1db94'
    },
    accent: {
      main: '#20173c'
    }
  }
}

export const BladeDarkBlueTheme = createTheme({
  palette: {
    mode: 'dark',
    text: {
      primary: '#f9f9fb'
    },
    primary: {
      main: '#0dbedc'
    },
    secondary: {
      main: '#0dbedc'
    },
    accent: {
      main: '#0018c'
    },
    error: {
      main: '#a00000'
    },
    background: {
      default: '#000',
      paper: '#1c1c1e'
    }
  }
})

export const BladeDarkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#b00000'
    },
    secondary: {
      main: '#00000'
    },
    accent: {
      main: '#20173c'
    },
    background: {
      default: '#030303',
      paper: '#111'
    }
  }
})

export const BladeDarkGreyTheme: Theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#333'
    },
    secondary: {
      main: '#222'
    },
    accent: {
      main: '#444'
    },
    background: {
      default: '#030303',
      paper: '#111'
    }
  }
})

export const BladeDarkOrangeTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#FFBF47'
    },
    secondary: {
      main: '#edad2d'
    },
    accent: {
      main: '#4281'
    },
    background: {
      default: '#030303',
      paper: '#111'
    }
  }
})

export const BladeDarkPinkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#bf026b'
    },
    secondary: {
      main: '#bf026b'
    },
    accent: {
      main: '#400729'
    },
    background: {
      default: '#030303',
      paper: '#111'
    }
  }
})

export const BladeLightRedTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#800000'
    },
    secondary: {
      main: '#800000'
    },
    accent: {
      main: '#a00000'
    },
    background: {
      default: '#fdfdfd',
      paper: '#eee'
    }
  }
})
export const BladeLightBlueTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#03a9f4'
    },
    secondary: {
      main: '#03a9f4'
    },
    accent: {
      main: '#0288d1'
    },
    background: {
      default: '#fdfdfd',
      paper: '#eee'
    }
  }
})

export const ledfxThemes = {
  Dark: BladeDarkTheme,
  DarkRed: BladeDarkTheme,
  DarkOrange: BladeDarkOrangeTheme,
  LightRed: BladeLightRedTheme,
  LightBlue: BladeLightBlueTheme,
  DarkGreen: BladeDarkGreenTheme,
  DarkBlue: BladeDarkBlueTheme,
  DarkGrey: BladeDarkGreyTheme,
  DarkPink: BladeDarkPinkTheme
} as any

/* eslint-disable @typescript-eslint/indent */
export const ledfxTheme =
  (window.localStorage.getItem('ledfx-theme')
    ? window.localStorage.getItem('ledfx-theme')
    : window.localStorage.getItem('hassTokens')
    ? 'DarkBlue'
    : window.location.origin === 'https://my.ledfx.app'
    ? 'DarkGreen'
    : isElectron()
    ? 'DarkOrange'
    : 'DarkBlue') || 'DarkBlue'
/* eslint-enable @typescript-eslint/indent */
