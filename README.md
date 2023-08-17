# Version Control System: `tea`

I made this VCS to learn the inner-working of a popular VCS, `git`. A video is p
provided below as a "demo" of this program. The steps and commands i used in the
video are provided below as test cases. Furthermore, the program below is made t
o run in Linux (specifically Arch Linux 64) only and further code modification m
ay be needed to run this program in other OSes.

## Steps

First, make an alias for easier usage

```bash
alias tea="/path/to/repo/tea"
```

Next, create an empty repository as a "sandbox environment". The steps used in t
he video are as below:

```bash
// test for tea init
tea init

// Create a file, then git status
echo -e "File 1\n" > file_01.txt
tea status

// Write to index file
tea add file_01.txt
tea status

// Commit a file
tea commit -m "initial commit"
tea status

// Update a file, then commit
echo -e "File 1" >> file_01.txt
tea status
tea add file_01.txt
tea commit -m "add second line"
tea status

// Test remove from index file
echo "File 2" > file_02.txt
tea add file_02.txt
tea status
tea rm file_02.txt
tea status

// Log
tea log

// Checkout
tea checkout [REFS] [FOLDER]

// .teaignore file
echo -e "File 3" > file_03.txt
echo file_03.txt > .teaignore
tea add .teaignore
tea commit -m ".gitignore initial commit"
tea check-ignore .

// View the project
tea ls-tree -r main
```

Other commands are available, albeit not shown in the demo due to certain circumstances:

```text
hash-object
ls-files
rev-parse
show-ref
tag
```

Video link: https://drive.google.com/drive/folders/1DsfRB3QwwWXu6o2md4lOGgGTu4JYEDS9?usp=drive_link

## Acknowledgements

- This project was inspired by one of the questions from the Distributed Systems
Laboratory Assistant Selection
- Many thanks to [Thibault Polge](https://wyag.thb.lt/) for providing a wonderful tutorial of writing a simple VCS.
- Many thanks to [yveschris](https://github.com/yveschris/possibly-the-fastest-analytical-inverse-of-vandermonde-matrices) for providing the vandermonde matrix inverse algorithm
- README template by [@flynerdpl](https://www.flynerd.pl/): [README](https://github.com/ritaly/README-cheatsheet)
