
set theme_dir $vTcl(VTCL_HOME)
set themes {
    clearlooks
    cornsilk-dark
    cornsilk-light
    notsodark
	notasdark
    page-cornsilkdark
    page-cornsilklight
    page-dark
    page-legacy
    page-light
    page-notsodark
 	page-sky
    page-wheat
    waldorf
    redLeather
}
	# page-grass

foreach theme $themes {
    set filename [file join $theme_dir themes $theme.tcl]
    catch {source $filename}
}

