import { definePreset } from '@primevue/themes';
import Aura from '@primevue/themes/aura';

const AuraCustom = definePreset(Aura, {
    semantic: {
        // font scale (text Tailwind text-{key} text）
        fontSize: {
            tiny: '0.75rem',       // ~10.5px  text,text
            small: '0.8125rem',    // ~11.4px  text
            caption: '0.875rem',   // ~12.25px font scale (text color-muted text）
            body: '1rem',          // 14px     text
            subtitle: '1.125rem', // ~14.9px  text
            title: '1.25rem',      // 17.5px   text,text
            heading: '1.5rem',     // 21px     text
            display: '1.875rem',   // 26.25px  text
            hero: '2rem'         // 35px     text
        },
        // font scale (text，text/text）
        rating: {
            high: '#6c3',
            medium: '#fc3',
            low: '#c33',
            none: '#bbb'
        },
        space: {
            page: '2rem',
            container: '0.75rem',
            section: '1.75rem',
            block: '1.5rem',
            item: '0.5rem',
            inline: '0.25rem',
            tight: '0.375rem',
            micro: '0.125rem'
        },
        size: {
            layoutMaxWidth: '1200px',
            headerHeight: '3.75rem',
            footerHeight: '3rem',
            contentHeight: 'calc(100dvh - var(--p-size-header-height) - var(--p-size-footer-height) - (var(--p-space-page) * 2) - 2px)',
            dialog: {
                sm: '400px',
                md: '600px',
                lg: '960px'
            },
            preview: {
                imageWidth: '84rem',
                imageHeight: '63rem',
                toolbar: {
                    paddingX: '0.25rem',
                    paddingY: '0.25rem',
                    gap: '0.25rem',
                    buttonSize: '2rem',
                    buttonPadding: '0.25rem',
                    radius: '{radius.item}'
                }
            },
            poster: {
                xxs: '4rem',
                tiny: '4.5rem',
                xs: '5rem',
                sm: '6rem',
                md: '7rem',
                lg: '18.75rem'
            },
            avatar: {
                md: '6rem',
                lg: '7rem'
            },
            control: {
                gap: '0.8rem',
                fieldHeightSm: '2.5rem',
                fieldHeightMd: '2.75rem',
                fieldHeightLg: '3rem',
                fieldHeightHero: '3rem',
                iconSize: '2rem',
                iconSizeSm: '1.5rem',
                badgeSize: '3rem',
                badgeSizeSm: '2.5rem',
                detailBadgeSize: '3.5rem',
                labelWidth: '5rem'
            },
            badge: {
                card: '{size.control.badgeSizeSm}',
                default: '{size.control.badgeSize}',
                detail: '{size.control.detailBadgeSize}'
            },
            tabs: {
                height: '2.5rem',
                contentMinHeight: '20rem',
                minWidth: '5.625rem',
                maxWidth: '13.75rem'
            },
            settings: {
                tabContentMinHeight: '40rem',
                systemTabContentMinHeight: '60rem',
                cardMinHeightCompact: '6rem',
                cardMinHeightRegular: '10rem',
                cardMinHeightTall: '16rem'
            },
            formField: {
                sm: '8rem',
                md: '12rem',
                lg: '16rem'
            },
            brandLogoWidth: '8rem',
            searchHeroWidth: '56rem',
            calendarTodayBadgeSize: '1.5rem',
            calendarDateRailWidth: '4rem',
            calendarCellMinHeight: '8rem',
            calendarCellHeight: '10rem',
            bottomDrawerHeight: '80vh',
            placeholder: {
                tiny: '2.5rem',
                xs: '6.5rem',
                sm: '7.5rem',
                summary: '7rem',
                action: '8.5rem',
                md: '12.5rem',
                lg: '18.75rem'
            }
        },
        typography: {
            fontSize: '14px'
        },
        brand: {
            fontFamily: '"Avenir Next Condensed", "Optima", "Candara", "Trebuchet MS", "Segoe UI", sans-serif',
            letterSpacing: '0.08em'
        },
        shadow: {
            content: '0 4px 12px -2px rgba(0, 0, 0, 0.08), 0 2px 6px -1px rgba(0, 0, 0, 0.04)',
            tab: '0 -2px 12px rgba(0, 0, 0, 0.06)',
            badge: '0 4px 10px -3px rgba(0, 0, 0, 0.18)'
        },
        radius: {
            container: '{border.radius.sm}',
            item: '{border.radius.sm}',
            badge: '0.75rem'
        },
        hover: {
            transform: {
                mediaImage: '1.05'
            }
        },
        transitionDuration: '0.2s',
        focusRing: {
            width: '1px',
            style: 'solid',
            color: '{primary.color}',
            offset: '2px',
            shadow: 'none'
        },
        disabledOpacity: '0.6',
        iconSize: '1rem',
        anchorGutter: '2px',
        primary: {
            50: '{red.50}',
            100: '{red.100}',
            200: '{red.200}',
            300: '{red.300}',
            400: '{red.400}',
            500: '{red.500}',
            600: '{red.600}',
            700: '{red.700}',
            800: '{red.800}',
            900: '{red.900}',
            950: '{red.950}'
        },
        formField: {
            paddingX: '0.5rem',
            paddingY: '0.25rem',

            borderRadius: '{radius.item}',
            focusRing: {
                width: '0',
                style: 'none',
                color: 'transparent',
                offset: '0',
                shadow: 'none'
            },
            transitionDuration: '{transition.duration}'
        },
        list: {
            padding: '0.25rem 0.25rem',
            gap: '2px',
            header: {
                padding: '0.5rem 0.625rem 0.25rem 0.625rem'
            },
            option: {
                padding: '0.2rem 0.375rem',
                borderRadius: '{border.radius.sm}'
            },
            optionGroup: {
                padding: '0.5rem 0.75rem',
                fontWeight: '600'
            }
        },
        content: {

            borderRadius: '{radius.container}'
        },
        mask: {
            transitionDuration: '0.3s'
        },
        navigation: {
            list: {
                padding: '0.25rem 0.25rem',
                gap: '2px'
            },
            item: {
                padding: '0.5rem 0.75rem',
                borderRadius: '{border.radius.sm}',
                gap: '0.5rem'
            },
            submenuLabel: {
                padding: '0.5rem 0.75rem',
                fontWeight: '600'
            },
            submenuIcon: {
                size: '0.875rem'
            }
        },
        overlay: {
            select: {
                borderRadius: '{border.radius.md}',
                shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)'
            },
            popover: {
                borderRadius: '{border.radius.md}',
                padding: '0.75rem',
                shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)'
            },
            modal: {
                borderRadius: '{border.radius.sm}',
                padding: '{spacing.container}',
                shadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)'
            },
            navigation: {
                shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)'
            }
        },
        colorScheme: {
            light: {
                surface: {
                    0: '#ffffff',
                    50: '{slate.50}',
                    100: '{slate.100}',
                    200: '{slate.200}',
                    300: '{slate.300}',
                    400: '{slate.400}',
                    500: '{slate.500}',
                    600: '{slate.600}',
                    700: '{slate.700}',
                    800: '{slate.800}',
                    900: '{slate.900}',
                    950: '{slate.950}'
                },
                primary: {
                    color: '{primary.600}',
                    contrastColor: '#ffffff',
                    hoverColor: '{primary.700}',
                    activeColor: '{primary.800}'
                },
                highlight: {
                    background: '{primary.50}',
                    focusBackground: '{primary.100}',
                    color: '{primary.700}',
                    focusColor: '{primary.800}'
                },
                mask: {
                    background: 'rgba(0,0,0,0.4)',
                    color: '{surface.200}'
                },
                formField: {
                    background: '{surface.0}',
                    disabledBackground: '{surface.200}',
                    filledBackground: '{surface.50}',
                    filledHoverBackground: '{surface.50}',
                    focusBackground: '{surface.0}',
                    borderColor: '{surface.200}',
                    hoverBorderColor: '{surface.300}',
                    focusBorderColor: '{primary.color}',
                    invalidBorderColor: '{red.400}',
                    color: '{surface.700}',
                    disabledColor: '{surface.400}',
                    placeholderColor: '{surface.400}',
                    invalidPlaceholderColor: '{red.400}'
                },
                text: {
                    color: '{surface.700}',
                    hoverColor: '{surface.800}',
                    mutedColor: '{surface.500}',
                    hoverMutedColor: '{surface.600}'
                },
                page: {
                    background: '{surface.50}'
                },
                content: {
                    background: '{surface.0}',
                    hoverBackground: '{surface.100}',
                    borderColor: '{surface.200}',
                    color: '{surface.700}',
                    hoverColor: '{surface.800}',
                    placeholderBackground: '{surface.100}',
                    borderSubtle: '{surface.100}'
                },
                mediaCard: {
                    movie: 'color-mix(in srgb, {yellow.400}, white 93%)',
                    tv: 'color-mix(in srgb, {green.300}, white 92%)'
                }
            },
            dark: {
                surface: {
                    0: '#ffffff',
                    50: '#fafafa',
                    100: '#f4f4f5',
                    200: '#e4e4e7',
                    300: '#d4d4d8',
                    400: '#a1a1aa',
                    500: '#71717a',
                    600: '#52525b',
                    700: '#27272a',
                    800: '#18181b',
                    900: '#09090b',
                    950: '#000000'
                },
                primary: {
                    color: '{primary.600}',
                    contrastColor: '{surface.900}',
                    hoverColor: '{primary.500}',
                    activeColor: '{primary.400}'
                },
                highlight: {
                    background: 'color-mix(in srgb, {primary.700}, transparent 90%)',
                    focusBackground: 'color-mix(in srgb, {primary.600}, transparent 84%)',
                    color: 'rgba(255,255,255,.87)',
                    focusColor: 'rgba(255,255,255,.87)'
                },
                mask: {
                    background: 'rgba(0,0,0,0.6)',
                    color: '{surface.200}'
                },
                formField: {
                    background: '{surface.950}',
                    disabledBackground: '{surface.800}',
                    filledBackground: '{surface.900}',
                    filledHoverBackground: '{surface.800}',
                    focusBackground: '{surface.950}',
                    borderColor: '{surface.700}',
                    hoverBorderColor: '{surface.600}',
                    focusBorderColor: '{primary.color}',
                    invalidBorderColor: '{red.400}',
                    color: '{surface.0}',
                    disabledColor: '{surface.400}',
                    placeholderColor: '{surface.400}',
                    invalidPlaceholderColor: '{red.400}'
                },
                text: {
                    color: '{surface.0}',
                    hoverColor: '{surface.0}',
                    mutedColor: '{surface.400}',
                    hoverMutedColor: '{surface.300}'
                },
                page: {
                    background: '{surface.950}'
                },
                content: {
                    background: '#111111',
                    hoverBackground: '#161616',
                    borderColor: '{surface.700}',
                    color: '{surface.0}',
                    hoverColor: '{surface.0}',
                    placeholderBackground: '{surface.800}',
                    borderSubtle: '{surface.700}'
                },
                mediaCard: {
                    movie: 'color-mix(in srgb, {yellow.300}, {surface.900} 96%)',
                    tv: 'color-mix(in srgb, {green.500}, {surface.950} 94%)'
                }
            }
        }
    }
});

export default AuraCustom;
