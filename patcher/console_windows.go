package main

import "syscall"

// setupConsole switches the console to UTF-8 so the Chinese messages show
// up on a default (code page 950/932) Windows console.
func setupConsole() {
	syscall.NewLazyDLL("kernel32.dll").NewProc("SetConsoleOutputCP").Call(65001)
}
